# Authentication and Authorization

FirecREST relies on well-known standards for authentication (AuthN) and authorization (AuthZ) layers with the idea of providing a way to easily integrate the API with extended technologies.

## Authentication

FirecREST enables OpenID Connect ([OIDC](https://openid.net/developers/how-connect-works/))/[OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc6749) as the standard for authentication. A JSON Web Tokens ([JWT](https://datatracker.ietf.org/doc/html/rfc7519)) is sent as the `Authorization` header [bearer token](https://datatracker.ietf.org/doc/html/rfc6750) with information related to the user that executes a command on the HPC system.

This JWT (also known as "[access token](https://datatracker.ietf.org/doc/html/rfc6749#section-1.4)") works as a credential to access the HPC facility.

This means that the HPC center using FirecREST must have access to an Identity Provider ([IdP](https://auth0.com/docs/authenticate/identity-providers)) that supports OIDC/OAuth2 Bearer Tokens for proper use of the API.

As IdPs that supports OIDC/OAuth2 we can find [Keycloak](https://www.keycloak.org/), [ShibbolethIdp](https://wiki.shibboleth.net/confluence/display/IDPPLUGINS/OIDC+OP), [Auth0](https://auth0.com/docs/authenticate/protocols/openid-connect-protocol), [WSO2 Identity Server](https://wso2.com/identity-and-access-management), among others.

### Token validation

FirecREST must be configured to use the public key of the IdP to check that the access token is valid and comes from a trusted source. This **offline validation** of the access token can also be complemented checking specific **scopes** in the token.

![f7t_authn_basic](../../../assets/img/authn_basics.svg)

FirecREST only requires an access token from a trusted IdP, therefore the **client application** consuming FirecREST can use any authorization grant defined in the OAuth2 protocol

- [Authorization code](https://datatracker.ietf.org/doc/html/rfc6749#section-4.1): used in UI applications (browser, mobile, etc).
- Implicit
- Password credentials, and
- [Client credentials](https://datatracker.ietf.org/doc/html/rfc6749#section-4.4)

**Client credential** type is especially important for APIs such as FirecREST, since it enables automated pipelines and workflows on HPC (for instance, a CI/CD pipeline that test a scientific library performs as expected on the HPC system every day).

You can see a list of use cases where client credentials is crucial [here](../../../use_cases/README.md).

## Authorization