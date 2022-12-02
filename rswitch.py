#!/usr/bin/env python3

from time import sleep, time
import os
from subprocess import DEVNULL, STDOUT, call
import sys
import uuid
import json
import pkg_resources

import click
import requests
from selenium import webdriver


CAASCAD_ZONES_URL = os.getenv('CAASCAD_ZONES_URL', "https://git.corp.caascad.com/terraform/envs-ng/raw/gen/zones_static/zones.json")

CONFIG_DIR = f"{os.getenv('HOME')}/.config/rswitch"
CAASCAD_ZONES_FILE = f"{CONFIG_DIR}/zones.json"
COOKIES_FILE = f"{CONFIG_DIR}/cookies.pkl"
KUBECONFIG_DIR = f"/run/user/{str(os.getuid())}/rswitch/{str(os.getppid())}/.kube"
TOKEN_TTL = 3600 * 24 * 7 # 1 week
ZONES_TTL = 60 * 30 # 30min


def setup():
    if not os.path.isdir(CONFIG_DIR):
        log("Looks like you are running kswitch for the first-time!")
        log(f"I'm going to create {CONFIG_DIR} for storing rswitch configurations.")
        try:
            debug(f"Create directory {CONFIG_DIR}")
            os.makedirs(CONFIG_DIR, exist_ok=True)
            os.makedirs(f"{CONFIG_DIR}/chrome", exist_ok=True)
        except OSError:
            error(f"Creation of the directory {CONFIG_DIR} failed")
    if not os.path.isdir(KUBECONFIG_DIR):
        log(
            f"I'm going to create {KUBECONFIG_DIR} to store Kubernetes configuration files."
        )
        try:
            debug(f"Create directory {KUBECONFIG_DIR}")
            os.makedirs(KUBECONFIG_DIR, exist_ok=True)
        except OSError:
            error(f"Creation of the directory {KUBECONFIG_DIR} failed")


def log(*args, **kwargs):
    output_fd = sys.stderr if os.getenv("RSWITCH_EXPORT") == "1" or os.getenv("RSWITCH_SILENCE") == "1" else sys.stdout
    if not os.getenv("RSWITCH_SILENCE") or os.getenv("RSWITCH_VERBOSE") == "1":
        print("\x1B[32m--- [INFO]", *args, "\x1B[0m", file=output_fd, **kwargs)


def debug(*args, **kwargs):
    output_fd = sys.stderr if os.getenv("RSWITCH_EXPORT") == "1" or os.getenv("RSWITCH_SILENCE") == "1" else sys.stdout
    if os.getenv("RSWITCH_VERBOSE") == "1":
        print("\x1B[34m--- [DEBUG]", *args, "\x1B[0m", file=output_fd, **kwargs)


def error(*args, **kwargs):
    print("\x1B[31m--- [ERROR]", *args, "\x1B[0m", file=sys.stderr, **kwargs)


def get_session_token(zone_list, zone_name):
    log("Use your browser to login to Rancher...")
    driver = webdriver.Firefox(service_log_path=f"{CONFIG_DIR}/geckodriver_service.log")
    debug("Launching browser...")
    domain_name = zone_list[zone_name]["domain_name"]
    driver.get(f"https://rancher.{zone_name}.{domain_name}")
    token = None
    while not token:
        sleep(2)
        debug("Checking cookies...")
        cookies = driver.get_cookies()
        for cookie in cookies:
            if cookie["name"] == "R_SESS":
                token = cookie["value"]
                log("Login successful !")

    debug("Closing browser")
    driver.close()
    return token


def generate_kubeconfig(zone_list, zone, cloud_zone, output, cache):
    log("Getting kubernetes token...")
    if cache:
        token = get_saved_token(cloud_zone)

    cloud_zone_domain_name = zone_list[cloud_zone]["domain_name"]
    if not cache or not token:
        session_token = get_session_token(zone_list, cloud_zone)
        debug("Requesting Rancher's token")
        endpoint = f"https://rancher.{cloud_zone}.{cloud_zone_domain_name}/v3/token"
        headers = {
            "content-type": "application/json",
            "Authorization": f"Bearer {session_token}",
        }
        data = {
            "current": False,
            "enabled": True,
            "expired": False,
            "isDerived": False,
            "ttl": TOKEN_TTL * 1000,
            "type": "token",
            "description": f"rswitch-{str(uuid.uuid4())}",
        }
        res = requests.post(endpoint, headers=headers, json=data).json()
        if not "token" in res:
            error("Can't parse Rancher token")
            sys.exit(1)
        token = res["token"]
        save_token(cloud_zone, token, (res["createdTS"] + res["ttl"]) / 1000)
    else:
        debug("Reusing cached token")
    if output:
        stdout = {
            "apiVersion": "client.authentication.k8s.io/v1beta1",
            "kind": "ExecCredential",
            "status": {
                "token": token
            }
        }
        print(json.dumps(stdout))
    else:
        cluster_id = get_cluster_id(zone_list,cloud_zone, token,
            "local" if cloud_zone == zone else "caascad-" + zone
        )
        log("Creating Kubernetes configuration file")
        create_config_file(
            url=f"https://rancher.{cloud_zone}.{cloud_zone_domain_name}/k8s/clusters/{cluster_id}",
            cluster=zone,
            user=cloud_zone,
            context=zone,
        )
        create_config_file(
            url=f"https://rancher.{cloud_zone}.{cloud_zone_domain_name}/k8s/clusters/{cluster_id}",
            cluster=zone,
            user=cloud_zone,
            context=zone,
            path=f"{KUBECONFIG_DIR}/config",
        )


def save_token(zone, token, expires_at):
    debug("Save token in cache")
    try:
        with open(f"{CONFIG_DIR}/.token", encoding='utf-8') as input_file:
            data = json.load(input_file)
    except:
        data = {}
    data[zone] = {"token": token, "expiresAt": expires_at}
    with open(f"{CONFIG_DIR}/.token", "w", encoding='utf-8') as output_file:
        json.dump(data, output_file)


def get_saved_token(zone):
    debug("Searching for a cached token...")
    if not os.path.isfile(f"{CONFIG_DIR}/.token"):
        debug("Token cache file not found")
        return None
    with open(f"{CONFIG_DIR}/.token", encoding='utf-8') as file:
        try:
            data = json.load(file)
            if not zone in data:
                debug("Token not found in cache", zone)
                return None
            if data[zone]["expiresAt"] < time():
                debug("Found an expired token")
                return None
            return data[zone]["token"]
        except:
            return None


def create_config_file(cluster, url, user, context="default", path=None):
    debug(f'Adding cluster in configuration file {path if path else "~/.kube/config"}')
    call(
        ["kubectl", "config"]
        + (["--kubeconfig", path] if path else [])
        + ["set-cluster", "rswitch-" + cluster, "--server", url],
        stdout=DEVNULL,
        stderr=STDOUT,
    )
    debug(f'Adding user in configuration file {path if path else "~/.kube/config"}')
    call(
        ["kubectl", "config"]
        + (["--kubeconfig", path] if path else [])
        + [
            "set-credentials",
            "rswitch-" + user,
            "--exec-api-version",
            "client.authentication.k8s.io/v1beta1",
            "--exec-command",
            "rswitch",
            "--exec-arg",
            "login",
            "--exec-arg",
            "-c",
            "--exec-arg",
            cluster
        ],
        stdout=DEVNULL,
        stderr=STDOUT,
    )
    debug(f'Adding context in configuration file {path if path else "~/.kube/config"}')
    call(
        ["kubectl", "config"]
        + (["--kubeconfig", path] if path else [])
        + [
            "set-context",
            "rswitch-" + context,
            "--cluster",
            "rswitch-" + cluster,
            "--namespace",
            "default",
            "--user",
            "rswitch-" + user,
        ],
        stdout=DEVNULL,
        stderr=STDOUT,
    )
    debug(f'Set default context in configuration file {path if path else "~/.kube/config"}')
    call(
        ["kubectl", "config"]
        + (["--kubeconfig", path] if path else [])
        + ["use-context", "rswitch-" + context],
        stdout=DEVNULL,
        stderr=STDOUT,
    )


def get_zones(cache):
    log("Getting zones list...")
    if cache:
        zone_list = get_saved_zone_list()
        if zone_list:
            return zone_list
    debug("Requesting zone list from remote server...")
    zone_list = requests.get(CAASCAD_ZONES_URL).json()
    save_zone_list(zone_list)
    return zone_list


def save_zone_list(zone_list):
    debug("Save zone list in cache")
    data = zone_list
    with open(f"{CONFIG_DIR}/.zones", "w", encoding='utf-8') as output_file:
        json.dump(data, output_file)


def get_saved_zone_list():
    debug("Searching for a cached zones list...")
    if not os.path.isfile(f"{CONFIG_DIR}/.zones"):
        debug("Zones cache file not found")
        return None
    if os.path.getmtime(f"{CONFIG_DIR}/.zones") + ZONES_TTL < time():
        debug("Zones cache file expired")
        return None
    with open(f"{CONFIG_DIR}/.zones", encoding='utf-8') as file:
        try:
            data = json.load(file)
            debug("Using cached zone list")
            return data
        except:
            return None


def get_cloud_zone(zone_list, zone):
    debug("Searching for cluster in caascad-zones")
    if not zone in zone_list.keys():
        error("Zone not found")
        sys.exit(1)
    return zone_list[zone]["parent_zone_name"] if zone_list[zone]["type"] == "client" else zone


def get_cluster_id(zone_list, zone_name, token, cluster_name):
    debug("Searching cluster in Rancher")
    domain_name = zone_list[zone_name]["domain_name"]
    endpoint = f"https://rancher.{zone_name}.{domain_name}/v3/clusters?limit=-1&sort=name"
    headers = {"content-type": "application/json", "Authorization": f"Bearer {token}"}
    res = requests.get(endpoint, headers=headers).json()
    for cluster in res["data"]:
        if cluster["name"] == cluster_name:
            return cluster["id"]
    error("Cluster not found in Rancher")
    sys.exit(1)


@click.group()
def main():
    pass


@main.command(
    context_settings={"ignore_unknown_options": True},
    help="kubectl wrapper that use the context initialised in this shell",
)
@click.argument("query", nargs=-1)
def kubectl(query):
    os.system(" ".join((f"KUBECONFIG={KUBECONFIG_DIR}/config", "kubectl") + query))


@main.command(
    context_settings={"ignore_unknown_options": True},
    help="helm wrapper that use the context initialised in this shell",
)
@click.argument("query", nargs=-1)
def helm(query):
    os.system(" ".join((f"KUBECONFIG={KUBECONFIG_DIR}/config", "helm") + query))


@main.command(help="Current rswitch version")
def version():
    version = pkg_resources.get_distribution('rswitch').version
    print(version)


@main.command(help="Login to a CAASCAD_ZONE and change kubectl context")
@click.option(
    "--command",
    "-c",
    is_flag=True
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable cache",
)
@click.option(
    "--export",
    "-e",
    envvar="RSWITCH_EXPORT",
    is_flag=True,
    help="Print environment varaibles export commands",
)
@click.option(
    "--verbose", "-v", envvar="RSWITCH_VERBOSE", is_flag=True, help="Debug mode"
)
@click.argument("zone_name")
def login(zone_name, export, verbose, no_cache, command):
    if verbose:
        os.environ["RSWITCH_VERBOSE"] = "1"
    if export:
        os.environ["RSWITCH_EXPORT"] = "1"
    if command:
        os.environ["RSWITCH_SILENCE"] = "1"

    cache = False if no_cache else True

    setup()
    zone_list = get_zones(cache)
    cloud_zone = get_cloud_zone(zone_list, zone_name)
    generate_kubeconfig(zone_list, zone_name, cloud_zone, output=command, cache=cache)
    if export:
        print(f"export KUBECONFIG={KUBECONFIG_DIR}/config")

if __name__ == "__main__":
    main()
