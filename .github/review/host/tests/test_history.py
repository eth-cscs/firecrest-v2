import copy
import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest


HELPER = Path(__file__).resolve().parents[1] / "history.py"
spec = importlib.util.spec_from_file_location("review_history", HELPER)
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)
REPO = "eth-cscs/firecrest-v2"
CREATED = "2026-10-01T12:00:00Z"
UPDATED = "2026-10-02T13:00:00Z"
HEAD = "a" * 40
ORIGINAL = "b" * 40


def connection(nodes=(), more=False, cursor=None):
    return {"nodes": list(nodes), "pageInfo": {"hasNextPage": more, "endCursor": cursor}}


def thread_page(value):
    return {"data": {"repository": {"pullRequest": {"reviewThreads": value}}}}


def review(identity=1, **changes):
    result = {
        "id": identity, "user": {"login": "review-bot[bot]", "type": "Bot"},
        "body": "Prior review", "state": "COMMENTED", "submitted_at": CREATED,
        "commit_id": HEAD, "html_url": f"https://github.com/{REPO}/pull/17#review-{identity}",
    }
    result.update(changes)
    return result


def conversation_comment(identity=1, **changes):
    result = {
        "id": identity, "user": {"login": "reviewer", "type": "User"},
        "body": "Please keep the previous review in mind", "created_at": CREATED,
        "updated_at": UPDATED, "html_url": f"https://github.com/{REPO}/pull/17#comment-{identity}",
    }
    result.update(changes)
    return result


def inline_comment(identity="comment-1", **changes):
    result = {
        "id": identity, "author": {"login": "review-bot[bot]", "__typename": "Bot"},
        "body": "Earlier inline finding", "createdAt": CREATED, "updatedAt": UPDATED,
        "url": f"https://github.com/{REPO}/pull/17#discussion-{identity}",
        "commit": {"oid": HEAD}, "originalCommit": {"oid": ORIGINAL},
        "replyTo": None, "pullRequestReview": {"fullDatabaseId": "41"},
        "diffHunk": "@@ -1 +1 @@\n-old\n+new", "path": "recipe/config.yaml",
        "line": 9, "originalLine": 7,
    }
    result.update(changes)
    return result


def thread(identity="thread-1", comments=None, **changes):
    result = {
        "id": identity, "path": "recipe/config.yaml", "line": 9, "originalLine": 7,
        "isOutdated": False, "isResolved": False, "resolvedBy": None,
        "comments": connection([inline_comment(f"{identity}-comment")], cursor="comment-end")
        if comments is None else comments,
    }
    result.update(changes)
    return result


class HistoryAPI:
    def __init__(self, reviews=(), conversations=(), threads=None, comments=None):
        self.reviews = list(reviews)
        self.conversations = list(conversations)
        self.threads = {None: connection()} if threads is None else threads
        self.comments = {} if comments is None else comments

    def __call__(self, path, payload=None):
        if payload is None:
            parsed = urlsplit(path)
            query = parse_qs(parsed.query)
            assert query["per_page"] == ["100"]
            page = int(query["page"][0])
            assert parsed.path in {f"/repos/{REPO}/pulls/17/reviews", f"/repos/{REPO}/issues/17/comments"}
            values = self.reviews if parsed.path.endswith("/reviews") else self.conversations
            return copy.deepcopy(values[(page - 1) * 100:page * 100])
        assert path == "/graphql"
        variables = payload["variables"]
        if "id" in variables:
            result = {"data": {"node": {"id": variables["id"], "comments":
                      self.comments[(variables["id"], variables["cursor"])]}}}
        else:
            assert {key: variables[key] for key in ("owner", "name", "number")} == {
                "owner": "eth-cscs", "name": "firecrest-v2", "number": 17,
            }
            result = thread_page(self.threads[variables["cursor"]])
        return copy.deepcopy(result)


def test_preserves_prior_reviews_conversation_and_complete_inline_attribution():
    root = inline_comment("root")
    reply = inline_comment("reply", author=None, replyTo={"id": "root"},
                           commit=None, originalCommit=None, pullRequestReview=None,
                           line=None, originalLine=None)
    api = HistoryAPI(
        reviews=[review(41, body="", state="APPROVED"),
                 review(42, user=None, state="DISMISSED", body="Dismissed but relevant")],
        conversations=[conversation_comment(51, user={"login": "helper[bot]", "type": "Bot"}),
                       conversation_comment(52, user=None)],
        threads={None: connection([
            thread(comments=connection([root, reply], cursor="reply-end"), isOutdated=True,
                   isResolved=True, resolvedBy={"login": "maintainer"}, line=None),
            thread("deleted-resolver", isResolved=True),
        ], cursor="thread-end")},
    )

    result = history.fetch_history(REPO, 17, api)

    reviews = {item["id"]: item for item in result["reviews"]}
    discussion = result["review_threads"][0]
    root, reply = discussion["comments"]
    # Approval with no prose and a dismissed review still carry review state.
    assert reviews[root["review_id"]]["state"] == "APPROVED"
    assert reviews[root["review_id"]]["body"] == ""
    assert reviews[42]["state"] == "DISMISSED"
    assert reviews[42]["author"] is None
    # Preserve who said what, which revision it concerned, and the reply chain.
    assert root["author_type"] == "Bot"
    assert root["commit_id"] == HEAD and root["original_commit_id"] == ORIGINAL
    assert reply["reply_to_id"] == root["id"]
    assert reply["author"] is None and reply["review_id"] is None
    assert reply["commit_id"] is None and reply["original_commit_id"] is None
    assert discussion["line"] is None and discussion["original_line"] == 7
    assert discussion["is_outdated"] and discussion["is_resolved"]
    assert discussion["resolved_by"] == "maintainer"
    assert result["conversation_comments"][0]["author_type"] == "Bot"
    assert result["conversation_comments"][1]["author"] is None
    assert result["review_threads"][1]["is_resolved"]
    assert result["review_threads"][1]["resolved_by"] is None


@pytest.mark.parametrize("count", [101, 200, 205])
def test_reads_all_rest_pages_including_empty_terminal_page(count):
    api = HistoryAPI(reviews=[review(i) for i in range(count)],
                     conversations=[conversation_comment(i) for i in range(count)])

    result = history.fetch_history(REPO, 17, api)

    assert [item["id"] for item in result["reviews"]] == list(range(count))
    assert [item["id"] for item in result["conversation_comments"]] == list(range(count))


def test_reads_over_100_threads_and_replies_on_first_and_later_thread_pages():
    first_comments = [inline_comment(f"first-{i}", replyTo={"id": "first-0"} if i else None)
                      for i in range(205)]
    last_comments = [inline_comment(f"last-{i}", author={"login": "human", "__typename": "User"})
                     for i in range(101)]
    threads = [thread(f"thread-{i}") for i in range(101)]
    threads[0]["comments"] = connection(first_comments[:100], True, "first-100")
    threads[-1]["comments"] = connection(last_comments[:100], True, "last-100")
    api = HistoryAPI(
        threads={None: connection(threads[:100], True, "threads-100"),
                 "threads-100": connection(threads[100:], cursor="threads-end")},
        comments={
            ("thread-0", "first-100"): connection(first_comments[100:200], True, "first-200"),
            ("thread-0", "first-200"): connection(first_comments[200:], cursor="first-end"),
            ("thread-100", "last-100"): connection(last_comments[100:], cursor="last-end"),
        },
    )

    result = history.fetch_history(REPO, 17, api)

    assert [item["id"] for item in result["review_threads"]] == [f"thread-{i}" for i in range(101)]
    assert [item["id"] for item in result["review_threads"][0]["comments"]] == [
        f"first-{i}" for i in range(205)]
    assert result["review_threads"][0]["comments"][-1]["reply_to_id"] == "first-0"
    assert [item["id"] for item in result["review_threads"][-1]["comments"]] == [
        f"last-{i}" for i in range(101)]
    assert result["review_threads"][-1]["comments"][-1]["author_type"] == "User"


@pytest.mark.parametrize("scope", ["threads", "comments"])
def test_partial_graphql_errors_reject_even_when_data_is_present(scope):
    api = HistoryAPI(
        threads={None: connection([thread(comments=connection([inline_comment()], True, "next"))],
                                 cursor="thread-end")},
        comments={("thread-1", "next"): connection([inline_comment("reply")], cursor="reply-end")},
    )

    def partial_api(path, payload=None):
        response = api(path, payload)
        if payload is not None and (("id" in payload["variables"]) == (scope == "comments")):
            response["errors"] = [{"message": "history access failed", "path": ["repository"]}]
        return response

    with pytest.raises(ValueError, match="GraphQL.*errors"):
        history.fetch_history(REPO, 17, partial_api)


@pytest.mark.parametrize("scope", ["threads", "comments"])
@pytest.mark.parametrize("fault", [
    "missing_page_info", "missing_nodes", "null_nodes", "null_node", "non_boolean_more",
    "missing_cursor", "empty_cursor", "numeric_cursor", "empty_more", "repeat_cursor",
    "cursor_cycle", "duplicate_nodes",
])
def test_rejects_malformed_or_nonprogressing_graphql_pagination(scope, fault):
    item = thread if scope == "threads" else inline_comment
    pages = {None: connection([item("one")], cursor="end")}
    page = pages[None]
    if fault == "missing_page_info":
        del page["pageInfo"]
    elif fault == "missing_nodes":
        del page["nodes"]
    elif fault == "null_nodes":
        page["nodes"] = None
    elif fault == "null_node":
        page["nodes"] = [None]
    elif fault == "non_boolean_more":
        page["pageInfo"]["hasNextPage"] = 1
    elif fault == "missing_cursor":
        del page["pageInfo"]["endCursor"]
    elif fault in {"empty_cursor", "numeric_cursor"}:
        page["pageInfo"]["endCursor"] = "" if fault == "empty_cursor" else 1
    elif fault == "empty_more":
        pages[None] = connection([], True, "next")
    else:
        pages[None] = connection([item("one")], True, "a")
        if fault == "repeat_cursor":
            pages["a"] = connection([item("two")], True, "a")
        elif fault == "cursor_cycle":
            pages["a"] = connection([item("two")], True, "b")
            pages["b"] = connection([item("three")], True, "a")
        else:
            pages["a"] = connection([item("one")], cursor="end")
    if scope == "threads":
        api = HistoryAPI(threads=pages)
    else:
        api = HistoryAPI(
            threads={None: connection([thread(comments=pages[None])], cursor="thread-end")},
            comments={("thread-1", cursor): page for cursor, page in pages.items() if cursor is not None},
        )

    with pytest.raises(ValueError):
        history.fetch_history(REPO, 17, api)


@pytest.mark.parametrize("scope", ["reviews", "conversation_comments"])
@pytest.mark.parametrize("fault", ["error_object", "repeated_page"])
def test_rejects_rest_error_objects_and_nonprogressing_pages(scope, fault):
    item = review if scope == "reviews" else conversation_comment
    endpoint = "/reviews?" if scope == "reviews" else "/comments?"
    api = HistoryAPI()

    def broken_api(path, payload=None):
        if payload is None and endpoint in path:
            if fault == "error_object":
                return {"message": "API failure"}
            return [item(i) for i in range(100)]
        return api(path, payload)

    with pytest.raises(ValueError):
        history.fetch_history(REPO, 17, broken_api)


@pytest.mark.parametrize("missing", ["repository", "pull_request", "thread_node"])
def test_inaccessible_graphql_objects_are_not_treated_as_empty_history(missing):
    api = HistoryAPI(threads={None: connection([
        thread(comments=connection([inline_comment()], True, "next")),
    ], cursor="thread-end")})

    def missing_api(path, payload=None):
        if payload is not None:
            if missing == "repository":
                return {"data": {"repository": None}}
            if missing == "pull_request":
                return {"data": {"repository": {"pullRequest": None}}}
            if "id" in payload["variables"]:
                return {"data": {"node": None}}
        return api(path, payload)

    with pytest.raises(ValueError):
        history.fetch_history(REPO, 17, missing_api)


def test_review_links_preserve_64_bit_database_ids():
    identity = 2**53 + 1
    api = HistoryAPI(
        reviews=[review(identity)],
        threads={None: connection([thread(comments=connection([
            inline_comment(pullRequestReview={"fullDatabaseId": str(identity)})
        ], cursor="comment-end"))], cursor="thread-end")},
    )
    result = history.fetch_history(REPO, 17, api)
    reviews = {item["id"]: item for item in result["reviews"]}
    comment = result["review_threads"][0]["comments"][0]
    assert reviews[comment["review_id"]]["id"] == identity
