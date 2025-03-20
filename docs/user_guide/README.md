# User Guide

- Authentication (OIDC)
- Explain how the Staging area works for External Transfers
- Difference between blocking and non-blocking data transfer
- Usage of API
  - Link to the API Ref
- Usage of SDK
  - Link to pyFirecREST Ref



## Authentication (OIDC)

FirecREST authentication implements the [OpenID Connect](https://auth0.com/docs/authenticate/protocols/openid-connect-protocol) standard.

To access most end-points (see [api reference](./openapi)) you need to provide a JWT authorization token. The JWT token needs to be put in the Authorization header.

```
Authorization: Bearer <token>
```
