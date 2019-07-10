
import json
import base64
import requests

from .utils import timestr2dtime


DEFAULT_REGISTRY = 'registry-1.docker.io'
DEFAULT_TAG = 'latest'


def image_str_to_dict(image):
    registry = ''

    parts = image.split('/', 1)
    if len(parts) > 1:
        if '.' in parts[0] or ':' in parts[0]:
            # highly likely this is a DNS name in the form example.com[:123]
            registry = parts[0]
            repo_tag = parts[1].split(':')
        else:
            repo_tag = image.split(':')
    else:
        repo_tag = parts[0].split(':')
    repository = repo_tag[0]
    if len(repo_tag) > 1:
        tag = repo_tag[1]
    else:
        tag = DEFAULT_TAG

    return {'registry': registry,
            'repository': repository,
            'tag': tag}


def image_dict_to_str(image):
    tag = image.get('tag')
    registry = image.get('registry')
    repository = image.get('repository')

    image_name = image.get('image-name', repository)
    if tag:
        image_name = ':'.join([image_name, tag])

    if 'image-name' in image and 'repository' in image:
        image_name = '/'.join([repository, image_name])

    if registry:
        image_name = '/'.join([registry, image_name])

    return image_name


def versiontuple(v):
    return tuple(map(int, (v.split('.'))))


def is_semantic_version(ver):
    try:
        versiontuple(ver)
        return True
    except ValueError:
        return False


def list_tags(image):
    """
    :param image: {'registry': '', 'repository': '', 'tag': ''}
    :return: dict, image tags
    """
    repo = image.get('repository')
    headers = authn_header(repo)
    url = '{registry}/v2/{repo}/tags/list'.format(
        registry=(image.get('registry') or DEFAULT_REGISTRY), repo=repo)
    response = requests.get(url, headers=headers, json=True)
    if not response.status_code == requests.codes.ok:
        raise Exception('Failed to list image tags: {}'.format(response.reason))
    return response.json()


def _authn_header_docker_io(repo):
    login_template = "https://auth.docker.io/token?" + \
                     "service=registry.docker.io&scope=repository:{repo}:pull"
    response = requests.get(login_template.format(repo=repo), json=True)
    response_json = response.json()
    token = response_json["token"]
    return {"Authorization": "Bearer {}".format(token)}


def _authn_header_creds(username, password):
    userpass = bytes(username + ':' + password, "utf-8")
    return {'Authorization': 'Baisc %s' % base64.b64encode(userpass).decode('ascii')}


def authn_header(repo=None, username=None, password=None):
    if username and password:
        return _authn_header_creds(username, password)
    elif repo:
        return _authn_header_docker_io(repo)
    else:
        raise Exception('repo or (username and password) must be given')


def new_image_semantic_tag(image):
    new_image = None
    ver_running = versiontuple(image.get('tag'))
    tags = list_tags(image)
    img_tags = []
    for tag in tags['tags']:
        try:
            img_tags.append(versiontuple(tag))
        except ValueError:
            pass
    if len(img_tags) == 0:
        raise Exception('No semantically versioned tags in the registry for semantically versioned running image.')
    last_ver = sorted(img_tags)[-1]
    if last_ver > ver_running:
        new_image = image.udpate({'tag': '.'.join(map(str, last_ver))})
    return new_image


def new_image_timestamp(image, timestamp):
    new_image = None
    manifest_v1 = get_manifest_v1(image)
    mtstamps = sorted([timestr2dtime(json.loads(x['v1Compatibility'])['created'])
                       for x in manifest_v1['history']], reverse=True)
    image_changed_at = mtstamps[0]
    if image_changed_at > timestamp:
        new_image = image
    return new_image


def _get_manifest(image, headers=None):
    """
    :param image: {'registry': '', 'repository': '', 'tag': ''}
    :return: dict, image manifest
    """
    reg_endpoint = 'https://' + (image.get('registry') or DEFAULT_REGISTRY)
    repo = image.get('repository', None)
    if not repo:
        raise Exception('Image repository is not provided.')
    tag = image.get('tag', 'latest')

    get_manifest_template = "{registry}/v2/{repo}/manifests/{tag}"
    if headers:
        headers.update(authn_header(repo))
    else:
        headers = authn_header(repo)
    url = get_manifest_template.format(registry=reg_endpoint, repo=repo, tag=tag)

    response = requests.get(url, headers=headers, json=True)
    if not response.status_code == requests.codes.ok:
        raise Exception('Failed to get image manifest: {}'.format(response.reason))
    return response.json()


def get_manifest_v1(image):
    return _get_manifest(image)


def get_manifest_v2(image):
    atypes = ["application/vnd.docker.distribution.manifest.list.v2+json",
              "application/vnd.docker.distribution.manifest.v2+json"]
    headers = {"accept": ','.join(atypes)}
    return _get_manifest(image, headers=headers)