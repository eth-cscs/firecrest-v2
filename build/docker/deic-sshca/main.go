package main

import (
	_ "embed"
	"sshca"
)

var (
	//go:embed ca.template
	tmpl string
)

func main() {
	publicKey, signer := sshca.GetSignerFromSshAgent()

	sshca.Config = sshca.Conf{
		Template:                  tmpl,
		HTMLTemplate:              "login",
		Verification_uri_template: "http://localhost:2280/%s\n",
		SSOTTL:                    "3m",
		RendevouzTTL:              "1m",
		SshListenOn:               "0.0.0.0:2221",
		WebListenOn:               "0.0.0.0:2280",

		CaConfigs: map[string]sshca.CaConfig{
			"demoCA": {
				Name:                   "Demo CA",
				Signer:                 signer,
				PublicKey:              publicKey,
				ClientID:               "Firecrest-v2",
				IntroSpectClientID:     "firecrest-test-client",
				IntroSpectClientSecret: "wZVHVIEd9dkJDh9hMKc6DTvkqXxnDttk",
				Op: sshca.Opconfig{
					Userinfo:             "http://keycloak:8080/auth/realms/kcrealm/protocol/openid-connect/userinfo",
					Introspect:           "http://keycloak:8080/auth/realms/kcrealm/protocol/openid-connect/token/introspect",
					Device_authorization: "",
					Token:                "http://keycloak:8080/auth/realms/kcrealm/protocol/openid-connect/token",
					Issuer:               "http://localhost:8080/auth/realms/kcrealm",
				},
			},
			"transport": {
				Signer: signer,
			},
		},
	}

	sshca.Sshca()
}
