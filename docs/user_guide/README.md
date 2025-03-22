# User Guide


- Explain how the Staging area works for External Transfers
- Difference between blocking and non-blocking data transfer
- Usage of API
  - Link to the API Ref
- Usage of SDK
  - Link to pyFirecREST Ref



## Authentication
FirecREST authentication follows the [OpenID Connect (OIDC)](https://auth0.com/docs/authenticate/protocols/openid-connect-protocol) standard.

To access most endpoints (see the [API reference](./openapi)), you must provide a JWT authorization token in the `Authorization` header:
```
Authorization: Bearer <token>
```

FirecREST authenticates users by verifying the JWT token’s signature against trusted certificates (see the [configuration](./setup/conf) section). If the JWT token is valid, FirecREST extracts the `username` or `preferred_username` claim to establish the user's identity and propagate it downstream (e.g., for SSH authentication).

To obtain a JWT token, you need a trusted Identity Provider that supports OAuth2 or OpenID Connect protocols. The FirecREST Docker Compose development environment (see the [Getting Started](./getting_started) section) includes a preconfigured [Keycloak](https://www.keycloak.org/) identity provider.

There are multiple grant flows available to obtain a JWT token. The most common ones are:

### Client Credentials Grant

This grant is used to authenticate an application (client) rather than an individual user. However, since HPC infrastructures typically require usage tracking, it is recommended to create a dedicated client for each user or project and assign a service account owned by the user/project to the client. 

**Important:**
Using the identity provider to associate a user or project with a client offers a secure and flexible way to map HPC internal users to FirecREST credentials:
**client credential ← service account ← user/project**

In this flow, the client submits its `client_id` and `client_secret` directly to the authorization server to obtain an access token and a refresh token.

```
curl --request POST \
  --url 'http://localhost:8080/auth/realms/kcrealm/protocol/openid-connect/token' \
  --header 'content-type: application/x-www-form-urlencoded' \
  --data grant_type=client_credentials \
  --data client_id=firecrest-test-client \
  --data client_secret=wZVHVIEd9dkJDh9hMKc6DTvkqXxnDttk
```

**Note:** The above `curl` command is configured to work with the provided Docker Compose environment.

### Authorization Code Grant

This grant is intended for web applications. The user's browser is redirected (HTTP 302) to the authorization server, which handles authentication (e.g., via username/password, two-factor authentication, etc.).

After successful authentication, the authorization server redirects the browser back to a pre-registered endpoint in the web application, passing an authorization code. The web application then uses its own credentials (`client_id` and `client_secret`) along with the authorization code to request an access token from the authorization server.

