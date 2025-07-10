package sshca

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"embed"
	"encoding/base64"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"html/template"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"slices"
	"strings"
	"sync"
	"time"

	"golang.org/x/crypto/ssh"
	"golang.org/x/crypto/ssh/agent"
)

type (
	appHandler func(http.ResponseWriter, *http.Request) error

	Provisioner struct {
		ConfigurationEndpoint string `json:"configurationEndpoint"`
	}

	Opconfig struct {
		Userinfo             string `json:"userinfo_endpoint"`
		Introspect           string `json:"introspection_endpoint"`
		Device_authorization string `json:"device_authorization_endpoint"`
		Token                string `json:"token_endpoint"`
		Issuer               string `json:"issuer"`
	}

	DeviceResponse struct {
		Device_code               string        `json:"device_code"`
		Expires_in                int64         `json:"expires"`
		Interval                  time.Duration `json:"interval"`
		User_code                 string        `json:"user_code"`
		Verification_uri          string        `json:"verification_uri"`
		Verification_uri_complete string        `json:"verification_uri_complete"`
	}

	TokenResponse struct {
		Scope        string `json:"scope,omitempty"`
		Access_token string `json:"access_token,omitempty"`
		Id_token     string `json:"id_token,omitempty"`
		TokenType    string `json:"token_type,omitempty"`
		Expires_in   int64  `json:"expires_in"`
	}

	IntrospectionResponse struct {
		Active    bool     `json:"active"`
		Scope     string   `json:"scope,omitempty"`
		Client_id string   `json:"client_id,omitempty"`
		TokenType string   `json:"token_type,omitempty"`
		Exp       int64    `json:"exp"`
		Iat       int64    `json:"iat"`
		Sub       string   `json:"sub,omitempty"`
		Aud       []string `json:"aud,omitempty"`
		Iss       string   `json:"iss,omitempty"`
	}

	CAParams struct {
		Ttl         int64
		Permissions ssh.Permissions
	}

	CaConfig struct {
		Fake, Hide                                                                         bool
		Id, Name, PublicKey                                                                string
		ClientID, ClientSecret, ConfigEndpoint, IntroSpectClientID, IntroSpectClientSecret string
		SSHTemplate, HTMLTemplate                                                          string
		DefaultPrincipals, AuthnContextClassRef                                            []string
		HashedPrincipal                                                                    bool
		MyAccessID                                                                         bool
		Op                                                                                 Opconfig   `json:"-"`
		Signer                                                                             ssh.Signer `json:"-"`
		CAParams                                                                           CAParams
		ScopeCAParams                                                                      map[string]CAParams
	}

	Conf struct {
		ServiceName, RelayingParty string
		HostCertificatePrincipals  []string
		WWW                        embed.FS
		Template, HTMLTemplate     string
		Verification_uri_template  string
		SSOTTL, RendevouzTTL       string
		SshPort                    string
		SshListenOn                string
		WebListenOn                string
		Principal                  string
		AuthnContextClassRef       string
		Assurance                  string
		CaConfigs                  map[string]CaConfig
		Cryptokilib                string
		Slot                       string
		NoOfSessions               int
	}

	idprec struct {
		EntityID     string
		DisplayNames map[string]string
	}
)

const (
	sseRetry = 1000
)

var (
	allowedKeyTypes = map[string]bool{
		"ssh-ed25519":                      true,
		"ssh-ed25519-cert-v01@openssh.com": true,
	}
	Config  Conf
	tmpl    *template.Template
	claims  = &rendezvous{}
	client  = &http.Client{Timeout: 2 * time.Second}
	funcMap = template.FuncMap{
		"PathEscape": url.PathEscape,
	}
	wasPassive           = errors.New("wasPassive")
	ssoTTL, rendevouzTTL time.Duration
)

func Sshca() {
	tmpl = template.Must(template.New("ca.template").Funcs(funcMap).Parse(Config.Template))
	ssoTTL, _ = time.ParseDuration(Config.SSOTTL)
	rendevouzTTL, _ = time.ParseDuration(Config.RendevouzTTL)
	claims.ttl = rendevouzTTL
	claims.cleanUp()
	Config.SshPort = Config.SshListenOn[strings.Index(Config.SshListenOn, ":")+1:]
	prepareCAs()
	go sshserver()

	http.HandleFunc("/favicon.ico", faviconHandler)
	http.Handle("/", appHandler(sshcaRouter))

	fmt.Println("Listening on port: " + Config.WebListenOn)
	err := http.ListenAndServe(Config.WebListenOn, nil)
	fmt.Println("err: ", err)
}

func faviconHandler(w http.ResponseWriter, r *http.Request) {
	http.ServeFileFS(w, r, Config.WWW, "/www/favicon.ico")
}

func sshcaRouter(w http.ResponseWriter, r *http.Request) (err error) {
	path := strings.Split(r.URL.Path+"//", "/")
	p := path[1]
	switch p { // handle /www /feedback /sso
	case "www":
		http.ServeFileFS(w, r, Config.WWW, r.URL.Path)
		return
	case "feedback":
		return feedbackHandler(w, r)
	case "sso": // returning from login
		return ssoHandler(w, r)
	case "pwdevice": // returning from login
		return pwdeviceHandler(w, r)
	case "pw": // returning from login
		return pwHandler(w, r)
	default:
		ca, ok := Config.CaConfigs[p]
		if ok { // handle /<ca>/.*
			p2 := path[2]
			switch p2 {
			case "config":
				jsonTxt, _ := json.MarshalIndent(ca, "", "    ")
				w.Header().Add("Content-Type", "application/json")
				w.Write(jsonTxt)
				return
			case "sign":
				return sshsignHandler(w, r)
			case "mindthegap":
				http.ServeFileFS(w, r, Config.WWW, "/www/mindthegap.html")
				return
				//	return mindthegap(w, r, ca)
			case "ri":
				return riHandler(w, r, ca)
			default:
				if err = mindthegapPassive(w, r, ca); err != nil {
					return
				}
				op := ""
				if ca.ClientID != "" {
					op = ca.Name
				}
				err = tmpl.ExecuteTemplate(w, ca.HTMLTemplate, map[string]any{"ca": ca, "op": op, "rp": Config.RelayingParty, "ri": "//" + r.Host + "/" + ca.Id + "/ri"})
				return
			}
		}
		if ci, ok := claims.get(p); ok { // see if it is a token
			return tokenHandler(w, r, p, ci)
		}
		err = tmpl.ExecuteTemplate(w, "listCAs", map[string]any{"config": Config.CaConfigs})
		return
	}
}

func prepareCAs() {
	for i, v := range Config.CaConfigs {
		if v.ConfigEndpoint != "" {
			v.Op = Opconfig{}
			resp, _ := http.Get(v.ConfigEndpoint)
			configJson, _ := io.ReadAll(resp.Body)
			json.Unmarshal(configJson, &v.Op)
		}
		if v.Signer == nil {
			pubkey, _, _, _, _ := ssh.ParseAuthorizedKey([]byte(v.PublicKey))
			privkeyLabel := base64.RawURLEncoding.EncodeToString(pubkey.(ssh.CryptoPublicKey).CryptoPublicKey().(ed25519.PublicKey)[:])
			if priv, ok := findPrivatekey(privkeyLabel); ok {
				v.Signer = hsmSigner{
					priv: priv,
					pub:  pubkey,
				}
			}
		}
		if v.HTMLTemplate == "" {
			v.HTMLTemplate = Config.HTMLTemplate
		}
		v.Id = i
		Config.CaConfigs[i] = v
	}

	if Config.CaConfigs["transport"].Signer == nil {
		log.Panic("Transport signer is nil")
	}
}

func (fn appHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	remoteAddr := r.RemoteAddr
	if ra, ok := r.Header["X-Forwarded-For"]; ok {
		remoteAddr = ra[0]
	}

	// log.Printf("%s %s %s %+v", remoteAddr, r.Method, r.Host, r.URL)
	starttime := time.Now()

	w.Header().Set("X-Frame-Options", "sameorigin")
	w.Header().Set("Content-Security-Policy", "frame-ancestors 'self'")
	w.Header().Set("X-XSS-Protection", "0")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

	err := fn(w, r)

	status := 200
	if err != nil {
		status = 500
		if err.Error() == "401" {
			status = 401
		}
		http.Error(w, err.Error(), status)
	} else {
		err = fmt.Errorf("OK")
	}

	//log.Printf("%s: %s", err, r.Header.Get("User-Agent"))
	log.Printf("%s %s %s %+v %1.3f %d %s", remoteAddr, r.Method, r.Host, r.URL, time.Since(starttime).Seconds(), status, err)
}

func riHandler(w http.ResponseWriter, r *http.Request, ca CaConfig) (err error) {
	r.ParseForm()
	token := claims.set("", certInfo{ca: ca.Id, eol: time.Now().Add(ssoTTL)})
	if ca.ClientID != "" {
		err = deviceflowHandler(w, r, token, ca, certInfo{})
		return
	}
	data := url.Values{}
	data.Set("state", token)
	if idp := r.Form.Get("entityID"); idp != "" {
		data.Set("idpentityid", idp)
	}
	if len(ca.AuthnContextClassRef) > 0 {
		data.Set("acr_values", strings.Join(ca.AuthnContextClassRef, " "))
	}
	http.Redirect(w, r, "/sso?"+data.Encode(), http.StatusFound)
	return
}

func tokenHandler(w http.ResponseWriter, r *http.Request, token string, ci certInfo) (err error) {
	ca := Config.CaConfigs[ci.ca]
	if ca.ClientID != "" {
		err = deviceflowHandler(w, r, token, ca, ci)
		return
	}
	ci.eol = time.Now().Add(ssoTTL)
	claims.set(token, ci)
	data := url.Values{}
	data.Set("state", token)
	if ci.idp != "" {
		data.Set("idpentityid", ci.idp)
	}
	if len(ca.AuthnContextClassRef) > 0 {
		data.Set("acr_values", strings.Join(ca.AuthnContextClassRef, " "))
	}
	http.Redirect(w, r, "/sso?"+data.Encode(), http.StatusFound)
	return
}

func ssoHandler(w http.ResponseWriter, r *http.Request) (err error) {
	r.ParseForm()
	token := r.Form.Get("state")
	ci, ok := claims.get(token)
	if ok {
		principal := r.Header.Get(Config.Principal)
		if Config.CaConfigs[ci.ca].Fake {
			principal = "a_really_fake_principal"
		}
		ci = setPrincipal(token, principal)
		return ssoFinalize(w, r, token, ci)
	}
	return
}

func pwdeviceHandler(w http.ResponseWriter, r *http.Request) (err error) {
	r.ParseForm()
	token := r.Form.Get("state")
	waitfor := principal
	if ci, ok := claims.get(token); ok && ci.pw != "" {
		waitfor = principalAndPassword
	}
	if ci, ok := claims.wait(token, waitfor); ok {
		return ssoFinalize(w, r, token, ci)
	}
	return
}

func getMyAccssIdCertInfo(ci certInfo, res IntrospectionResponse) certInfo {

	ci.principals = []string{res.Sub}
	ci.params = Config.CaConfigs[ci.ca].CAParams
	if scope := getEFPScope(res.Scope); scope != "" {
		ci.principals = append(ci.principals, scope+"-"+res.Sub)
		if params, ok := Config.CaConfigs[ci.ca].ScopeCAParams[scope]; ok {
			ci.params = params
		}
	}
	ci.eol = time.Now().Add(rendevouzTTL)
	return ci
}

func getEFPScope(scopeList string) (res string) {
	const pre = "urn:geant:efp.core.aai.geant.org:res:"
	const cab = ":act:ssh"
	scopes := strings.Split(scopeList, " ")
	if i := slices.IndexFunc(scopes, func(s string) bool { return strings.HasPrefix(s, pre) }); i >= 0 {
		if tmp, ok := strings.CutPrefix(scopes[i], pre); ok {
			if tmp, ok := strings.CutSuffix(tmp, cab); ok {
				return tmp
			}
		}
	}
	return res
}

func setPrincipal(token, principal string) (ci certInfo) {
	ci, ok := claims.get(token)
	if ok {
		ca := Config.CaConfigs[ci.ca]
		ci.principals = []string{principal}
		if username := usernameFromPrincipal(principal, ca); username != "" {
			ci.principals = append(ci.principals, username)
		}
		ci.params = ca.CAParams
		ci.eol = time.Now().Add(rendevouzTTL)
		claims.set(token, ci)
	}
	return
}

func ssoFinalize(w http.ResponseWriter, r *http.Request, token string, ci certInfo) (err error) {
	ca := Config.CaConfigs[ci.ca]
	if len(ci.principals) > 0 {
		wantedAcrs := ca.AuthnContextClassRef
		acrs := strings.Split(r.Header.Get(Config.AuthnContextClassRef), ",")
		acrs = append(acrs, strings.Split(r.Header.Get(Config.Assurance), ",")...)
		if len(wantedAcrs) > 0 && intersectionEmpty(wantedAcrs, acrs) {
			return fmt.Errorf("no valid AuthnContextClassRef found: %v vs. %v", wantedAcrs, acrs)
		}
		if ci.pw != "" {
			if tmp, err := r.Cookie("pw"); err != nil || tmp.Value != ci.pw {
				err = tmpl.ExecuteTemplate(w, "pw", map[string]any{"token": token})
				return err
			}
			ci.pw = ""
			claims.set(token, ci)
			err = tmpl.ExecuteTemplate(w, "certificate", map[string]any{"token": token})
			return
		}
		err = tmpl.ExecuteTemplate(w, ca.HTMLTemplate, map[string]any{"ci": ci, "ca": ca, "state": token, "sshport": Config.SshPort, "rp": Config.RelayingParty, "ri": "//" + r.Host + "/" + ca.Id + "/ri"})
	}
	return
}

func pwHandler(w http.ResponseWriter, r *http.Request) (err error) {
	path := strings.Split(r.URL.Path+"//", "/")
	token := path[2]
	defer r.Body.Close()
	r.ParseForm()
	if ci, ok := claims.get(token); ok && ci.pw == r.Form.Get("pw") {
		http.SetCookie(w, &http.Cookie{Name: "pw", Value: ci.pw, Path: "/", Secure: true, HttpOnly: true, MaxAge: 86400, SameSite: http.SameSiteNoneMode})
		ci.pw = ""
		claims.set(token, ci)
		err = tmpl.ExecuteTemplate(w, "certificate", map[string]any{"token": token})
		return
	}
	err = tmpl.ExecuteTemplate(w, "pw", map[string]any{"token": token})
	return
}

func feedbackHandler(w http.ResponseWriter, r *http.Request) (err error) {
	path := strings.Split(r.URL.Path+"//", "/")
	token := path[2]
	w.Header().Set("X-Accel-Buffering", "no")
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")

	ci, ok := claims.wait(token, principal)
	if !ok {
		http.Error(w, "StatusServiceUnavailable", 503)
		return
	}
	w.(http.Flusher).Flush()
	if ci, ok = claims.wait(token, certificate); !ok {
		return
	}
	fmt.Fprintf(w, "event: certready\n%s\n\n", certPP(ci.cert, "data: "))
	return
}

func sshsignHandler(w http.ResponseWriter, r *http.Request) (err error) {
	params := struct {
		PublicKey string // don't use []byte - will be json interpreted as base64
		OTT       string
	}{}
	defer r.Body.Close()
	r.ParseForm()
	path := strings.Split(r.URL.Path, "/")
	ca := path[1]
	config, ok := Config.CaConfigs[ca]
	if !ok {
		return fmt.Errorf("CA not found: %s", ca)
	}
	req, _ := io.ReadAll(r.Body)
	err = json.Unmarshal(req, &params)
	if err != nil {
		fmt.Println("err", err)
		return
	}
	publicKey, _, _, _, err := ssh.ParseAuthorizedKey([]byte(params.PublicKey))
	if err != nil {
		return
	}

	res, err := introspect(params.OTT, config)
	if err != nil {
		return
	}

	ci := getMyAccssIdCertInfo(certInfo{ca: ca}, res)
	sshCertificate, err := newCertificate(config, publicKey, ci)
	if err != nil {
		return
	}
	cert := ssh.MarshalAuthorizedKey(sshCertificate)
	w.Write(cert)
	return
}

func introspect(token string, ca CaConfig) (res IntrospectionResponse, err error) {
	data := url.Values{}
	data.Set("token", token)
	data.Set("client_id", ca.IntroSpectClientID)
	data.Set("client_secret", ca.IntroSpectClientSecret)
	data.Set("scope", "openid email profile eduperson_entitlement urn:geant:efp.core.aai.geant.org:res:it4i.cz:act:ssh")

	request, _ := http.NewRequest("POST", ca.Op.Introspect, strings.NewReader(data.Encode()))
	request.Header.Add("Content-Type", "application/x-www-form-urlencoded")
	resp, err := client.Do(request)
	if err != nil {
		return
	}
	defer resp.Body.Close()
	responsebody, err := io.ReadAll(resp.Body)
	if err != nil {
		return
	}

	res = IntrospectionResponse{}
	err = json.Unmarshal(responsebody, &res)
	if err != nil {
		return res, errors.New("json parsing error")
	}

	if slices.Index(res.Aud, ca.ClientID) < 0 {
		return IntrospectionResponse{}, errors.New("aud mismatach")
	}

	if !res.Active {
		return IntrospectionResponse{}, errors.New("inactive")
	}

	now := time.Now().Unix()
	if res.Iat > now || res.Exp <= now {
		return IntrospectionResponse{}, errors.New("token timeout")
	}

	if res.Iss != ca.Op.Issuer {
		return IntrospectionResponse{}, errors.New("issuer mismatch")
	}
	return
}

func mindthegapCheckIDPName(w http.ResponseWriter, r *http.Request, ca string) (entityIDJSON string, err error) {
	r.ParseForm()
	cookieName := "mindthegap"
	if _, ok := r.Form["entityID"]; ok {
		entityIDJSON = r.Form.Get("entityIDJSON")
		http.SetCookie(w, &http.Cookie{Name: cookieName, Value: base64.URLEncoding.EncodeToString([]byte(entityIDJSON)), Path: "/" + ca, Secure: true, MaxAge: 34560000})
		return
	}
	if tmp, err := r.Cookie(cookieName); err == nil {
		if data, err := base64.StdEncoding.DecodeString(tmp.Value); err == nil {
			entityIDJSON = string(data)
			return entityIDJSON, err
		}
	}
	return "", wasPassive
}

func mindthegapPassive(w http.ResponseWriter, r *http.Request, ca CaConfig) (err error) {
	if ca.ClientID != "" || ca.Fake {
		return
	}
	if _, err = mindthegapCheckIDPName(w, r, ca.Id); err == nil {
		return
	}
	discoURL := "https://wayf.wayf.dk/ds/?"
	dsParams := url.Values{}
	dsParams.Set("return", "https://"+r.Host+"/"+ca.Id)
	dsParams.Set("entityID", Config.RelayingParty)
	dsParams.Set("policy", "mindthegap,v2")
	dsParams.Set("isPassive", "true")
	dsParams.Set("return", "https://"+r.Host+"/"+ca.Id)
	http.Redirect(w, r, discoURL+dsParams.Encode(), http.StatusFound)
	return wasPassive
}

func mindthegap(w http.ResponseWriter, r *http.Request, ca CaConfig) (err error) {
	caURL := "https://" + r.Host + "/" + ca.Id
	riURL := caURL + "/ri"
	if ca.ClientID != "" {
		err = tmpl.ExecuteTemplate(w, "mindthegap", map[string]string{"idpName": ca.Name, "riURL": riURL})
		return
	}
	entityIDJSON, _ := mindthegapCheckIDPName(w, r, ca.Id)
	discoURL := "https://wayf.wayf.dk/ds/?"
	idpName := "Access through your Institution"
	dsParams := url.Values{}
	dsParams.Set("return", caURL+"/mindthegap")
	dsParams.Set("entityID", Config.RelayingParty)
	dsParams.Set("policy", "mindthegap,v2")
	idp := idprec{}
	errr := json.Unmarshal([]byte(entityIDJSON), &idp)
	if errr == nil && idp.EntityID != "" {
		idpName = idp.DisplayNames["en"]
		riURL += "?entityID=" + url.QueryEscape(idp.EntityID)
		if _, ok := r.Form["entityID"]; ok {
			http.Redirect(w, r, riURL, http.StatusFound)
			return
		}
	} else {
		riURL = discoURL + dsParams.Encode()
	}
	dsParams.Set("policy", "v2")
	p := map[string]string{"idpName": idpName, "riURL": riURL, "discoURL": discoURL + dsParams.Encode()}
	err = tmpl.ExecuteTemplate(w, "mindthegap", p)
	return
}

func sshserver() {
	sshConfig := &ssh.ServerConfig{
		// Remove to disable public key auth.
		PublicKeyCallback: func(c ssh.ConnMetadata, pubKey ssh.PublicKey) (*ssh.Permissions, error) {
			if !allowedKeyTypes[pubKey.Type()] {
				return nil, errors.New("xxx")
			}
			permissions := &ssh.Permissions{
				Extensions: map[string]string{
					"pubkey": string(pubKey.Marshal()),
					"user":   c.User(),
				},
			}
			if c.User() == "demo" {
				if _, ok := pubKey.(*ssh.Certificate); !ok {
					return nil, errors.New("xxx")
				}
			}
			return permissions, nil
		},
	}
	hostSigner, err := newHostSigner(Config.CaConfigs["transport"].Signer, Config.ServiceName, Config.HostCertificatePrincipals)
	if err != nil {
		log.Fatal("failed to create hostSigner: ", err)
	}
	sshConfig.AddHostKey(hostSigner)
	//	sshConfig.AddHostKey(Config.CaConfigs["transport"].Signer)

	// Once a ServerConfig has been configured, connections can be
	// accepted.
	listener, err := net.Listen("tcp", Config.SshListenOn)
	if err != nil {
		log.Fatal("failed to listen for connection: ", err)
	}
	fmt.Println("ssh listening on " + Config.SshListenOn)

	for {
		nConn, err := listener.Accept()
		if err != nil {
			log.Println("failed to accept incoming connection: ", err)
			continue
		}
		go handleSSHConnection(nConn, sshConfig)
	}
}

func handleSSHConnection(nConn net.Conn, sshConfig *ssh.ServerConfig) {
	type tokenType uint8
	const (
		normal tokenType = iota
		device
	)

	conn, chans, reqs, err := ssh.NewServerConn(nConn, sshConfig)
	if err != nil {
		log.Println("failed to handshake: ", err)
		return
	}
	defer conn.Close()

	xtras := conn.Permissions.Extensions
	publicKey, _ := ssh.ParsePublicKey([]byte(xtras["pubkey"]))
	user := xtras["user"]

	// The incoming Request channel must be serviced.
	go ssh.DiscardRequests(reqs)

	for newChannel := range chans {
		if newChannel.ChannelType() != "session" {
			newChannel.Reject(ssh.UnknownChannelType, "unknown channel type")
			return
		}

		channel, reqs, err := newChannel.Accept()
		if err != nil {
			log.Println("Could not accept channel", err)
		}

		for req := range reqs {
			switch req.Type {
			case "exec":
				args := strings.Split(string(req.Payload[4:])+"  ", " ") // always at least 2 elements
				cmd, token := args[0], args[1]
				switch cmd {
				case "demo":
					demoCert(channel, publicKey)
					channel.Close()
					return
				case "ca":
					f1 := flag.NewFlagSet("", flag.ExitOnError)
					ca := f1.String("ca", "", "")
					idp := f1.String("idp", "", "")
					pw := f1.String("pw", "", "")
					f1.Parse(args[1:])

					_, ok := Config.CaConfigs[*ca]
					if *ca != "" && !ok {
						io.WriteString(channel, "unknown ca\n")
						channel.Close()
						return

					}
					if len(*pw) < 6 {
						io.WriteString(channel, "pw to short\n")
						channel.Close()
						return
					}
					token = claims.set("", certInfo{ca: *ca, idp: *idp, pw: *pw, eol: time.Now().Add(rendevouzTTL)})
					io.WriteString(channel, fmt.Sprintf(Config.Verification_uri_template, token))
				case "token": // fall thru below code common to ca and token
				}
				ci, ok := claims.wait(token, principal)
				if ok && user != "" && ci.cert == nil {
					cert, err := newCertificate(Config.CaConfigs[ci.ca], publicKey, ci)
					if err == nil {
						certTxt := ssh.MarshalAuthorizedKey(cert)
						fmt.Fprintf(channel, "%s", certTxt)
						ci.cert = cert
						claims.set(token, ci)
					}
				}
				channel.Close()
			case "shell":
				channel.Close()
			}
		}
	}
}

func newHostSigner(signer ssh.Signer, keyId string, principals []string) (hostSigner ssh.Signer, err error) {
	now := time.Now().In(time.FixedZone("UTC", 0)).Unix()
	cert := &ssh.Certificate{
		CertType:        ssh.HostCert,
		Key:             signer.PublicKey(),
		KeyId:           keyId,
		ValidPrincipals: principals,
		ValidAfter:      uint64(now - 60),
		ValidBefore:     uint64(now + 31556926),
	}
	err = cert.SignCert(rand.Reader, signer)
	return ssh.NewCertSigner(cert, signer)
}

func demoCert(channel ssh.Channel, publicKey ssh.PublicKey) {
	if cert, ok := publicKey.(*ssh.Certificate); ok {
		channel.Write(certPP(cert, ""))
		io.WriteString(channel, "\n")
		signatureKey := strings.TrimRight(string(ssh.MarshalAuthorizedKey(cert.SignatureKey)), "\n")
		signedByUs := false
		ca := ""
		for i, v := range Config.CaConfigs {
			if v.Signer == nil {
				continue
			}
			if signedByUs = signatureKey == v.PublicKey; signedByUs {
				ca = i
				break
			}
		}
		if !signedByUs {
			fmt.Fprintln(channel, "Certificate is not signed by this service")
		} else {
			fmt.Fprintf(channel, `Certificate is signed by the "%s" CA%s`, ca, "\n")
		}

		// from ssh.certs.go CheckCert
		unixNow := time.Now().Unix()
		if after := int64(cert.ValidAfter); after < 0 || unixNow < int64(cert.ValidAfter) {
			fmt.Fprintln(channel, `Certificate is not yet valid`)
		}
		if before := int64(cert.ValidBefore); cert.ValidBefore != uint64(ssh.CertTimeInfinity) && (unixNow >= before || before < 0) {
			fmt.Fprintln(channel, `Certificate has expired`)
		}
		// from ssh.certs.go - bytesForSigning
		c2 := *cert
		c2.Signature = nil
		out := c2.Marshal()
		// Drop trailing signature length.
		bytesForSigning := out[:len(out)-4]

		if err := cert.SignatureKey.Verify(bytesForSigning, cert.Signature); err != nil {
			fmt.Fprintln(channel, "Certificate signature does not verify")
		}
	}
}

func newCertificate(ca CaConfig, pubkey ssh.PublicKey, ci certInfo) (cert *ssh.Certificate, err error) {
	if _, ok := pubkey.(*ssh.Certificate); ok {
		pubkey = pubkey.(*ssh.Certificate).Key
	}

	now := time.Now().In(time.FixedZone("UTC", 0)).Unix()
	cert = &ssh.Certificate{
		CertType:        ssh.UserCert,
		Key:             pubkey,
		Permissions:     ci.params.Permissions,
		KeyId:           ci.principals[0],
		ValidPrincipals: ci.principals,
		ValidAfter:      uint64(now - 60),
		ValidBefore:     uint64(now + ci.params.Ttl),
	}
	err = cert.SignCert(rand.Reader, ca.Signer)
	return
}

func usernameFromPrincipal(principal string, ca CaConfig) (username string) {
	if ca.HashedPrincipal {
		hashed := sha256.Sum256([]byte(principal))
		username = strings.TrimLeft(base64.RawURLEncoding.EncodeToString(hashed[:24]), "-") // - (dash) not allowed as 1st character
		return
	}
	if ca.MyAccessID {
		username = strings.ReplaceAll(principal[:36], "-", "")
		return
	}
	return
}

func certPP(cert *ssh.Certificate, prefix string) (pp []byte) {
	const iso = "2006-01-02T15:04:05"
	va := time.Unix(int64(cert.ValidAfter), 0).Format(iso)
	vb := time.Unix(int64(cert.ValidBefore), 0).Format(iso)
	//hours := rec.cert.ValidBefore - cert.ValidAfter
	pp, _ = json.MarshalIndent(cert, prefix, "    ")
	pp = append([]byte(prefix), pp...) // no prefix on 1st line ???
	pp = regexp.MustCompile(`("ValidAfter": )(\d+),`).ReplaceAll(pp, []byte(`${1}`+va+`,`))
	pp = regexp.MustCompile(`("ValidBefore": )(\d+),`).ReplaceAll(pp, []byte(`${1}`+vb+`,`))
	return pp
}

// PP - super simple Pretty Print - using JSON
func PP(i ...interface{}) {
	for _, e := range i {
		switch v := e.(type) {
		case []byte:
			fmt.Println(string(v))
		default:
			s, _ := json.MarshalIndent(v, "", "    ")
			fmt.Println(string(s))
		}
	}
	return
}

// rendezvous

const (
	principal = iota
	certificate
	principalAndPassword
)

type (
	certInfo struct {
		ca         string
		idp        string
		pw         string
		principals []string
		params     CAParams
		cert       *ssh.Certificate
		eol        time.Time
	}

	rendezvous struct {
		info sync.Map
		ttl  time.Duration
	}
)

func (rv *rendezvous) cleanUp() {
	ticker := time.NewTicker(rendevouzTTL)
	go func() {
		for {
			<-ticker.C
			rv.info.Range(func(k, v interface{}) bool {
				if v.(certInfo).eol.Before(time.Now()) {
					rv.info.Delete(k)
				}
				return true
			})
		}
	}()
}

func (rv *rendezvous) set(token string, ci certInfo) string {
	if token == "" {
		token = rand.Text()
	}
	if ci.eol.IsZero() {
		ci.eol = time.Now().Add(rv.ttl)
	}
	rv.info.Store(token, ci)
	return token
}

func (rv *rendezvous) get(token string) (ci certInfo, ok bool) {
	a, ok := rv.info.Load(token)
	if ok {
		ci = a.(certInfo)
		if ci.eol.Before(time.Now()) {
			rv.info.Delete(token)
			return ci, false
		}
	}
	return
}

func (rv *rendezvous) wait(token string, cond int) (ci certInfo, ok bool) {
	ticker := time.NewTicker(time.Second)
	for {
		ci, ok = rv.get(token)
		if !ok || (cond == principal && len(ci.principals) > 0 && ci.pw == "") || (cond == certificate && ci.cert != nil) || (cond == principalAndPassword && len(ci.principals) > 0 && ci.pw != "") {
			return
		}
		<-ticker.C
	}
}

// ssh-agent

func GetSignerFromSshAgent() (pubkey string, signer ssh.Signer) {
	socket := os.Getenv("SSH_AUTH_SOCK")
	conn, err := net.Dial("unix", socket)
	if err != nil {
		log.Fatalf("Failed to open SSH_AUTH_SOCK: %v", err)
	}
	agent := agent.NewClient(conn)
	signers, err := agent.Signers()
	if err != nil {
		log.Panicf("Getting signers from ssh-agent failed: %v", err)
	}
	for _, s := range signers {
		if allowedKeyTypes[s.PublicKey().Type()] {
			pubkey = strings.TrimRight(string(ssh.MarshalAuthorizedKey(s.PublicKey())), "\n")
			signer = s
			return
		}
	}
	log.Fatalln("No ed25519 keys available in ssh-agent")
	return
}

func intersectionEmpty(s1, s2 []string) (res bool) {
	hash := make(map[string]bool)
	for _, e := range s1 {
		hash[e] = true
	}
	for _, e := range s2 {
		if hash[e] {
			return false
		}
	}
	return true
}
