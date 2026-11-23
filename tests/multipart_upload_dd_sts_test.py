# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

import hashlib
import hmac
import json
import subprocess
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "docs/user_guide/file_transfer_bash/examples/multipart_upload_dd_sts.sh"
)


class MockServer(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.requests = []
        self.failure = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def respond(self, status, body=b"", headers=None):
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_request(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.requests.append((self.command, self.path, dict(self.headers), body))
        url = urlsplit(self.path)
        query = parse_qs(url.query, keep_blank_values=True)
        if url.path == "/token":
            self.respond(200, b'{"access_token":"fake-token"}')
        elif url.path == "/filesystem/cluster/transfer/upload":
            self.respond(
                200,
                json.dumps(
                    {
                        "transferDirectives": {
                            "maxPartSize": 5242880,
                            "stsCredentials": {
                                "accessKeyId": "test-key",
                                "secretAccessKey": "test-secret",
                                "sessionToken": "test-session",
                            },
                        }
                    }
                ).encode(),
            )
        elif self.command == "POST" and "uploads" in query:
            self.respond(
                200,
                b"<InitiateMultipartUploadResult><UploadId>id+/=</UploadId>"
                b"</InitiateMultipartUploadResult>",
            )
        elif self.command == "PUT":
            headers = {} if self.server.failure == "missing-etag" else {
                "ETag": f'"tag&<{query["partNumber"][0]}>"'
            }
            self.respond(200, headers=headers)
        elif self.command == "POST" and "uploadId" in query:
            body = (
                b"<Error><Code>InvalidPart</Code></Error>"
                if self.server.failure == "complete"
                else b"<CompleteMultipartUploadResult/>"
            )
            self.respond(200, body)
        elif self.command == "DELETE":
            self.respond(204)
        else:
            self.respond(404)

    do_POST = handle_request
    do_PUT = handle_request
    do_DELETE = handle_request


class MultipartSTSExampleTest(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join)
        self.addCleanup(self.server.shutdown)
        self.directory = Path(self.tmp.name)
        self.data = b"a" * 5242880 + b"last part"
        self.file = self.directory / "input file"
        self.file.write_bytes(self.data)
        endpoint = f"http://127.0.0.1:{self.server.server_port}"
        self.env = self.directory / "env"
        self.env.write_text(
            f"TOKEN_URI={endpoint}/token\n"
            f"F7T_URL={endpoint}\n"
            f"S3_URL={endpoint}\n"
            "CLIENT_ID=test-client\nCLIENT_SECRET=test-secret\n"
            "BUCKET=test-user\nS3_OBJECT_KEY='folder/space + file'\n"
        )

    def run_script(self):
        return subprocess.run(
            ["bash", str(SCRIPT), str(self.file), "cluster", "/destination", str(self.env)],
            text=True,
            capture_output=True,
            timeout=30,
        )

    def assert_s3_signature(self, method, path, headers):
        headers = {key.lower(): value for key, value in headers.items()}
        authorization = headers["authorization"]
        fields = dict(
            item.strip().split("=", 1)
            for item in authorization.removeprefix("AWS4-HMAC-SHA256 ").split(",")
        )
        signed_headers = fields["SignedHeaders"].split(";")
        canonical_headers = "".join(
            f"{name}:{' '.join(headers[name].split())}\n" for name in signed_headers
        )
        url = urlsplit(path)
        canonical_query = "&".join(sorted(url.query.split("&")))
        canonical_request = "\n".join(
            [
                method,
                url.path,
                canonical_query,
                canonical_headers,
                fields["SignedHeaders"],
                headers["x-amz-content-sha256"],
            ]
        )
        scope = fields["Credential"].split("/", 1)[1]
        date, region, service, _ = scope.split("/")
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                headers["x-amz-date"],
                scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        key = b"AWS4test-secret"
        for value in (date, region, service, "aws4_request"):
            key = hmac.new(key, value.encode(), hashlib.sha256).digest()
        signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(fields["Signature"], signature)

    def test_uploads_parts_and_completes_with_sts(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        requests = self.server.requests
        api_request = json.loads(requests[1][3])
        self.assertEqual(api_request["transferDirectives"]["accessMethod"], "sts")
        s3_requests = requests[2:]
        self.assertEqual([r[0] for r in s3_requests], ["POST", "PUT", "PUT", "POST"])
        for method, path, headers, _ in s3_requests:
            self.assertTrue(path.startswith("/test-user/folder/space%20%2B%20file?"))
            self.assertIn("Credential=test-key/", headers["Authorization"])
            self.assertEqual(headers["x-amz-security-token"], "test-session")
            self.assert_s3_signature(method, path, headers)
        self.assertEqual(s3_requests[1][3], self.data[:5242880])
        self.assertEqual(s3_requests[2][3], self.data[5242880:])
        self.assertEqual(
            parse_qs(urlsplit(s3_requests[1][1]).query)["uploadId"], ["id+/="]
        )
        root = ET.fromstring(s3_requests[3][3])
        parts = list(root)
        self.assertEqual(
            [(list(part)[0].text, list(part)[1].text) for part in parts],
            [("1", '"tag&<1>"'), ("2", '"tag&<2>"')],
        )
        self.assertIn("object remains in S3", result.stdout)

    def test_missing_etag_aborts_upload(self):
        self.server.failure = "missing-etag"
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("did not return an ETag", result.stderr)
        self.assertEqual(self.server.requests[-1][0], "DELETE")

    def test_completion_error_aborts_upload(self):
        self.server.failure = "complete"
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("InvalidPart", result.stderr)
        self.assertEqual(self.server.requests[-1][0], "DELETE")


if __name__ == "__main__":
    unittest.main()
