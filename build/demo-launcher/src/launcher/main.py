from contextlib import asynccontextmanager
import os
import sys
from packaging.version import Version
from fastapi import Depends, FastAPI, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import asyncssh
from fastapi.security import HTTPBasic, HTTPBasicCredentials
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


sys.path.append("../../../src")
sys.path.append("../")
from firecrest.config import FileSystem
from lib.ssh_clients.ssh_client import SSHClient
from firecrest.config import FileSystemDataType


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

    print("Navigate to http://localhost:8080/ to get started!\n\n")

    yield


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic(auto_error=False)
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


def ping(host):
    command = ["ping", "-c", "1", host]
    return subprocess.call(command) == 0


async def sshClient(username, sshkey_private, sshkey_cert_public):
    demo_cluster = settings.clusters[0]
    options = asyncssh.SSHClientConnectionOptions(
        username=username,
        client_keys=[sshkey_private],
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

    return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/realms/kcrealm/protocol/openid-connect/token")
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

    return {"access_token": token, "token_type": "bearer"}


@app.get("/certs")
def download_certificate():
    return {"keys": [get_jwk()]}


@app.get("/auth/realms/kcrealm/protocol/openid-connect/auth")
def auth(state: str):

    # 1 https://auth-tds.cscs.ch/auth/realms/cscs/protocol/openid-connect/auth?scope=openid+profile+email&response_type=code&client_id=firecrest-web-ui-v2-tds&redirect_uri=https://firecrest-web-ui-v2.tds.cscs.ch/auth/callback&state=09e9d3b1-8331-478b-9cac-7856c6d0ebc9
    # 2 https://auth-tds.cscs.ch/auth/realms/cscs/login-actions/authenticate?session_code=LB7-kU-rwkcYQYdCqYYeRULW9mLqvjDh4UfwkWYwmQo&execution=33b67c08-d21d-4d1d-9a00-1f574069d7f6&client_id=firecrest-web-ui-v2-tds&tab_id=A-oZrlT1WHw
    # 3 https://firecrest-web-ui-v2.tds.cscs.ch/auth/callback?state=09e9d3b1-8331-478b-9cac-7856c6d0ebc9&session_state=8b9ca80c-825c-4290-88c7-3507657f6094&iss=https://auth-tds.cscs.ch/auth/realms/cscs&code=f239fba7-ca21-4ac5-a39f-1612acbea8e7.8b9ca80c-825c-4290-88c7-3507657f6094.f41d2904-9ba3-4506-a46b-9089a8e90cf4

    #
    # https://auth-tds.cscs.ch/auth/realms/cscs/login-actions/authenticate?session_code=HPEMesZI4d86UQBirVZPLRMQLYJhBrJxGreSCILEHnk&execution=33b67c08-d21d-4d1d-9a00-1f574069d7f6&client_id=firecrest-web-ui-v2-tds&tab_id=JP4BaiH44cQ
    # https://firecrest-web-ui-v2.tds.cscs.ch/auth/callback?

    redirect_url = f"http://localhost:3000/auth/callback?state={state}&iss=http://localhost:8080/realms/kcrealm&code=8349988e-8cbf-45d6-a77e-1c74265446cc.cbad517e-9d56-42a5-8242-b53d17655747.f41d2904-9ba3-4506-a46b-9089a8e90cf4"

    return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)


class Scheduler(BaseModel):
    cluster_name: str


@app.post("/boot")
async def boot(scheduler: Scheduler):

    username = next(iter(settings.ssh_credentials))
    credentials = settings.ssh_credentials[username]

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
        if credentials.public_cert:
            sshkey_cert_public = asyncssh.import_certificate(credentials.public_cert)

        client = await sshClient(username, sshkey_private, sshkey_cert_public)
        sinfo = SinfoVersionCommand()
        version = await client.execute(sinfo)
        scheduler_campatible = Version(version) > Version("22.05")
    except Exception as e:
        raise HTTPException(status_code=400, detail=repr(e)) from e

    server = ServerProxy("http://dummy:dummy@localhost:9001/RPC2")

    state = server.supervisor.getProcessInfo("firecrest")

    if state["statename"] == "RUNNING":
        server.supervisor.stopProcess("firecrest")

    server.supervisor.startProcess("firecrest")

    token = generate_token(username)

    # TODO: check for slurm version and throw an error if it's to old. <22

    return {
        "message": "Firecrest v2 started successfully.",
        "access_token": token,
        "system_name": demo_cluster.name,
        "scheduler": {
            "type": "Slurm",
            "version": version,
            "is_compatible": scheduler_campatible,
        },
    }


class Credentials(BaseModel):
    username: str
    private_key: str
    public_cert: Optional[str] = None
    passphrase: Optional[str] = None


@app.post("/credentials")
async def credentials(credentials: Credentials):

    if not credentials.username:
        raise HTTPException(status_code=400, detail="Provide a valid username")

    demo_cluster = settings.clusters[0]
    sshkey_cert_public = ()
    sshkey_private = None

    try:
        sshkey_private = asyncssh.import_private_key(
            credentials.private_key, passphrase=credentials.passphrase
        )
        if credentials.public_cert:
            sshkey_cert_public = asyncssh.import_certificate(credentials.public_cert)

        ssh_credential = UnsafeSSHUserKeys(
            **{
                "private_key": credentials.private_key,
                "public_cert": credentials.public_cert,
                "passphrase": credentials.passphrase,
            }
        )
        settings.ssh_credentials.clear()
        settings.ssh_credentials[credentials.username] = ssh_credential

        client = await sshClient(
            credentials.username, sshkey_private, sshkey_cert_public
        )
        pwd = PwdCommand()
        user_home = await client.execute(pwd)

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
            if not ping(ssh_connection.proxyhost):
                raise HTTPException(
                    status_code=400, detail="Unable to ping ssh proxy hostname"
                )
        else:
            if not ping(ssh_connection.hostname):
                raise HTTPException(
                    status_code=400, detail="Unable to ping login node hostname"
                )

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
