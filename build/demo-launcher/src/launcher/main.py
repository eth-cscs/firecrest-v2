from contextlib import asynccontextmanager
import os
import sys
import socket
from packaging.version import Version
from fastapi import Depends, FastAPI, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, field_validator, SecretStr
import asyncssh
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2PasswordBearer


import jwt
from datetime import datetime, timedelta
from typing import Annotated, Any, Optional
from jose.utils import base64url_encode
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import yaml
from xmlrpc.client import ServerProxy
from launcher.config import (
    UnsafeSSHClientPool,
    UnsafeSSHUserKeys,
    UnsafeServiceAccount,
    UnsafeSettings,
)
import subprocess


from launcher.pwd_command import PwdCommand
from launcher.sinfo_command import SinfoVersionCommand
from launcher.qstat_command import QstatVersionCommand


sys.path.append("../../../src")
sys.path.append("../")
from firecrest.config import FileSystem
from firecrest.config import FileSystemDataType
from lib.ssh_clients.ssh_client import SSHClient
from lib.models.config_model import LoadFileSecretStr


keys = {}


@asynccontextmanager
async def lifespan(app: FastAPI):

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    keys["private_key_pem"] = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()
    keys["public_key"] = public_key
    keys["public_numbers"] = public_numbers
    keys["kid"] = "42"  # unique key identifier

    print(
        """
███████╗██╗██████╗ ███████╗ ██████╗██████╗ ███████╗███████╗████████╗   ██╗   ██╗██████╗ 
██╔════╝██║██╔══██╗██╔════╝██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝   ██║   ██║╚════██╗
█████╗  ██║██████╔╝█████╗  ██║     ██████╔╝█████╗  ███████╗   ██║█████╗██║   ██║ █████╔╝
██╔══╝  ██║██╔══██╗██╔══╝  ██║     ██╔══██╗██╔══╝  ╚════██║   ██║╚════╝╚██╗ ██╔╝██╔═══╝ 
██║     ██║██║  ██║███████╗╚██████╗██║  ██║███████╗███████║   ██║       ╚████╔╝ ███████╗
╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝        ╚═══╝  ╚══════╝

██████╗ ███████╗███╗   ███╗ ██████╗                                
██╔══██╗██╔════╝████╗ ████║██╔═══██╗                               
██║  ██║█████╗  ██╔████╔██║██║   ██║                               
██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║                               
██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝                               
╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝                                
██╗      █████╗ ██╗   ██╗███╗   ██╗ ██████╗██╗  ██╗███████╗██████╗ 
██║     ██╔══██╗██║   ██║████╗  ██║██╔════╝██║  ██║██╔════╝██╔══██╗
██║     ███████║██║   ██║██╔██╗ ██║██║     ███████║█████╗  ██████╔╝
██║     ██╔══██║██║   ██║██║╚██╗██║██║     ██╔══██║██╔══╝  ██╔══██╗
███████╗██║  ██║╚██████╔╝██║ ╚████║╚██████╗██║  ██║███████╗██║  ██║
╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
    """
    )

    print("Navigate to http://localhost:8025/ to get started!\n\n")

    yield


app = FastAPI(lifespan=lifespan)


origins = [
    "http://localhost",
    "http://localhost:8025",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
settings = UnsafeSettings()


def get_jwk():
    jwk_data = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": keys["kid"],
        "n": base64url_encode(
            keys["public_numbers"].n.to_bytes(
                (keys["public_numbers"].n.bit_length() + 7) // 8, byteorder="big"
            )
        ),
        "e": base64url_encode(
            keys["public_numbers"].e.to_bytes(
                (keys["public_numbers"].e.bit_length() + 7) // 8, byteorder="big"
            )
        ),
    }
    return jwk_data


def generate_token(username: str):
    expiration = datetime.utcnow() + timedelta(days=360)
    payload = {
        "sub": f"{username}-client",
        "name": username,
        "username": username,
        "preferred_username": username,
        "scope": "firecrest-v2 profile email",
        "exp": expiration,
    }
    headers = {"kid": keys["kid"]}
    token = jwt.encode(
        payload, keys["private_key_pem"], algorithm="RS256", headers=headers
    )
    return token


def check_ssh_socket(hostname, port=22):
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.connect((hostname, port))
    except Exception as ex:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to establish connection with {hostname} on port {port}",
        ) from ex
    else:
        test_socket.close()
    return True


async def sshClient(username, sshkey_private, passphrase, sshkey_cert_public):
    demo_cluster = settings.clusters[0]
    options = asyncssh.SSHClientConnectionOptions(
        username=username,
        client_keys=[sshkey_private],
        passphrase=passphrase,
        client_certs=[sshkey_cert_public],
        known_hosts=None,
    )

    proxy = ()
    if demo_cluster.ssh.proxy_host:
        proxy = await asyncssh.connect(
            host=demo_cluster.ssh.proxy_host,
            port=demo_cluster.ssh.proxy_port,
            options=options,
        )

    conn = await asyncssh.connect(
        host=demo_cluster.ssh.host,
        port=demo_cluster.ssh.port,
        options=options,
        tunnel=proxy,
    )
    return SSHClient(conn)


@app.get("/auth/realms/default/protocol/openid-connect/auth")
def auth(state: str, redirect_uri: str):
    redirect_url = f"{redirect_uri}?state={state}&code=secret-code"
    return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)


@app.post("/auth/realms/default/protocol/openid-connect/token")
@app.post("/token")
def get_token(
    credentials: Annotated[Optional[HTTPBasicCredentials], Depends(security)],
    grant_type: Optional[str] = Form(default=None),
    client_id: Optional[str] = Form(default=None),
    client_secret: Optional[str] = Form(default=None),
):
    username: str = None
    if client_id:
        username = client_id
    if credentials and credentials.username:
        username = credentials.username

    token = generate_token(username)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 31556952,
        "refresh_token": token,
    }


@app.get("/auth/realms/default/protocol/openid-connect/userinfo")
def userinfo_endpoint(token: Annotated[str, Depends(oauth2_scheme)]):

    payload = jwt.decode(token, keys["public_key"], algorithms=["RS256"])
    username = payload.get("name")
    if "username" in payload:
        username = payload.get("username")
    return {
        "id": username,
        "username": username,
        "preferred_username": username,
        "firstName": username,
        "lastName": "client",
        "email": username,
    }


@app.get("/certs")
def download_certificate():
    return {"keys": [get_jwk()]}


class Scheduler(BaseModel):
    cluster_name: str
    scheduler_type: str


@app.post("/boot")
async def boot(scheduler: Scheduler):

    username = next(iter(settings.ssh_credentials.keys))
    credentials = settings.ssh_credentials.keys[username]

    demo_cluster = settings.clusters[0]
    demo_cluster.name = scheduler.cluster_name

    dump: dict[str, Any] = settings.model_dump()
    settings_file = os.getenv("YAML_CONFIG_FILE", None)
    with open(settings_file, "w") as yaml_file:
        yaml.dump(dump, yaml_file)

    scheduler_campatible: bool = True
    try:
        sshkey_private = asyncssh.import_private_key(
            credentials.private_key, passphrase=credentials.passphrase
        )
        sshkey_cert_public = ()
        if credentials.public_cert:
            sshkey_cert_public = asyncssh.import_certificate(credentials.public_cert)

        client = await sshClient(
            username, sshkey_private, credentials.passphrase, sshkey_cert_public
        )

        if scheduler.scheduler_type == "pbs":
            qstat = QstatVersionCommand()
            version = await client.execute(qstat)
            scheduler_campatible = Version(version) == Version("23.06.06")
        elif scheduler.scheduler_type == "slurm":
            sinfo = SinfoVersionCommand()
            version = await client.execute(sinfo)
            scheduler_campatible = Version(version) > Version("22.05")
        else:
            scheduler_campatible = False

    except Exception as e:
        raise HTTPException(status_code=400, detail=repr(e)) from e

    server = ServerProxy("http://dummy:dummy@localhost:9001/RPC2")

    state = server.supervisor.getProcessInfo("firecrest")
    if state["statename"] == "RUNNING":
        server.supervisor.stopProcess("firecrest")
    server.supervisor.startProcess("firecrest")

    state = server.supervisor.getProcessInfo("firecrest-ui")
    if state["statename"] == "RUNNING":
        server.supervisor.stopProcess("firecrest-ui")
    server.supervisor.startProcess("firecrest-ui")

    token = generate_token(username)

    return {
        "message": "Firecrest v2 started successfully.",
        "access_token": token,
        "system_name": demo_cluster.name,
        "scheduler": {
            "type": scheduler.scheduler_type,
            "version": version,
            "is_compatible": scheduler_campatible,
        },
    }


class Credentials(BaseModel):
    username: str
    private_key: str
    public_cert: Optional[str] = None
    passphrase: Optional[str] = None

    @field_validator("*")
    @classmethod
    def empty_as_none(cls, v):
        return v or None if isinstance(v, (str,)) else v


@app.post("/credentials")
async def credentials(credentials: Credentials):

    if not credentials.username:
        raise HTTPException(status_code=400, detail="Provide a valid username")

    # Set OIDC client for web-ui
    with open("/app/config/webui-client", "a") as f:
        f.write(credentials.username)

    demo_cluster = settings.clusters[0]
    sshkey_cert_public = ()
    sshkey_private = None

    try:
        sshkey_private = asyncssh.import_private_key(
            credentials.private_key, passphrase=credentials.passphrase
        )
        if credentials.public_cert:
            sshkey_cert_public = asyncssh.import_certificate(credentials.public_cert)

        user_credentials = dict()
        user_credentials["private_key"] = credentials.private_key
        if credentials.public_cert:
            user_credentials["public_cert"] = credentials.public_cert
        if credentials.passphrase:
            user_credentials["passphrase"] = credentials.passphrase

        ssh_credential = UnsafeSSHUserKeys(
            **{
                "keys": {
                    credentials.username: user_credentials
                }
            }
        )
        
        settings.ssh_credentials = ssh_credential

        client = await sshClient(
            credentials.username,
            sshkey_private,
            credentials.passphrase,
            sshkey_cert_public,
        )
        pwd = PwdCommand()
        user_home = (await client.execute(pwd)).removesuffix("/" + credentials.username)

        file_system = FileSystem(
            **{
                "path": user_home,
                "data_type": FileSystemDataType.users,
                "default_work_dir": True,
            }
        )

        service_account = UnsafeServiceAccount(
            **{"client_id": credentials.username, "secret": ""}
        )

        demo_cluster.service_account = service_account
        demo_cluster.file_systems = [file_system]

    except Exception as e:
        raise HTTPException(status_code=400, detail=repr(e)) from e

    return {"message": "Credentials saved successfully.", "user_home": user_home}


class SSHConnection(BaseModel):
    hostname: str
    hostport: int
    proxyhost: Optional[str] = None
    proxyport: Optional[int] = None


@app.post("/sshconnection")
async def ssh_connection(ssh_connection: SSHConnection):
    try:

        if ssh_connection.proxyhost:
            check_ssh_socket(ssh_connection.proxyhost, ssh_connection.proxyport)
        else:
            check_ssh_socket(ssh_connection.hostname, ssh_connection.hostport)

        demo_cluster = settings.clusters[0]
        ssh_client_pool = UnsafeSSHClientPool(
            **{
                "host": ssh_connection.hostname,
                "port": ssh_connection.hostport,
                "proxy_host": ssh_connection.proxyhost,
                "proxy_port": ssh_connection.proxyport,
            }
        )
        demo_cluster.ssh = ssh_client_pool

    except Exception as e:
        raise HTTPException(status_code=400, detail=repr(e)) from e

    return {"message": "SSH hosts saved successfully."}


app.mount(
    "/",
    StaticFiles(directory="/app/launcher/static", html=True),
    name="static-play",
)
