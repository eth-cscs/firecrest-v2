# Authentication and Authorization

FirecREST relies on well-known standards for authentication (AuthN) and authorization (AuthZ) layers with the idea of providing a way to easily integrate the API with current technologies.

## Authentication

FirecREST uses OpenID Connect ([OIDC](https://openid.net/developers/how-connect-works/))/OAuth 2.0 as the standard for authentication. A JSON Web Tokens ([JWT](https://datatracker.ietf.org/doc/html/rfc7519)) is sent as the `Authorization` header [bearer token](https://datatracker.ietf.org/doc/html/rfc6750) with information related to the user that would execute a command on the HPC system.

This means that the HPC center using FirecREST must have access to an Identity Provider ([IdP](https://auth0.com/docs/authenticate/identity-providers)) that handles OIDC/OAuth2 Bearer Tokens for proper use of the API.

![f7t_authn_basic](../../../assets/img/authn_basics.svg)

