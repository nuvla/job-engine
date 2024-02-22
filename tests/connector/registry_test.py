import unittest
from mock import Mock

import nuvla.job_engine.connector.registry
from nuvla.job_engine.connector.registry import (image_str_to_dict,
                                      image_dict_to_str,
                                      new_image_semantic_tag)


class TestRegistry(unittest.TestCase):

    def test_image_str_to_dict(self):

        image = image_str_to_dict('registry.com/repo:1.2.3')
        assert image['registry'] == 'registry.com'
        assert image['image-name'] == 'repo'
        assert image['tag'] == '1.2.3'

        image = image_str_to_dict('registry.com/repo/name:1.2.3')
        assert image['registry'] == 'registry.com'
        assert image['repository'] == 'repo'
        assert image['image-name'] == 'name'
        assert image['tag'] == '1.2.3'

        image = image_str_to_dict('registry.com/repo/name')
        assert image['registry'] == 'registry.com'
        assert image['repository'] == 'repo'
        assert image['image-name'] == 'name'
        assert image['tag'] == 'latest'

        image = image_str_to_dict('repo')
        assert image['image-name'] == 'repo'
        assert image['tag'] == 'latest'

        image = image_str_to_dict('repo/name')
        assert image['repository'] == 'repo'
        assert image['image-name'] == 'name'
        assert image['tag'] == 'latest'

        image = image_str_to_dict('repo:1.2.3')
        assert image['image-name'] == 'repo'
        assert image['tag'] == '1.2.3'

        image = image_str_to_dict('repo/name:1.2.3')
        assert image['repository'] == 'repo'
        assert image['image-name'] == 'name'
        assert image['tag'] == '1.2.3'

    def test_image_dict_to_str(self):
        # FIXME: remove when 'image-name' is removed from component definition
        image = image_dict_to_str({'registry': '',
                                   'repository': 'repo',
                                   'image-name': 'name',
                                   'tag': ''})
        assert image == 'repo/name'

        image = image_dict_to_str({'image-name': 'name',
                                   'repository': 'repo',
                                   'tag': '0.0.1'})
        assert image == 'repo/name:0.0.1'

        image = image_dict_to_str({'registry': '',
                                   'repository': 'repo',
                                   'tag': ''})
        assert image == 'repo'

        image = image_dict_to_str({'registry': '',
                                   'repository': 'repo',
                                   'tag': '1.2.3'})
        assert image == 'repo:1.2.3'

        image = image_dict_to_str({'registry': 'registry.com',
                                   'repository': 'repo',
                                   'tag': '1.2.3'})
        assert image == 'registry.com/repo:1.2.3'

        image = image_dict_to_str({'registry': 'registry.com',
                                   'repository': 'repo/name',
                                   'tag': '1.2.3'})
        assert image == 'registry.com/repo/name:1.2.3'

    def test_new_image_semantic_tag(self):
        nuvla.job_engine.connector.registry.list_tags = Mock(return_value={'tags': ['0.0.1', '0.0.2']})
        image = new_image_semantic_tag({'tag': '0.0.1'})
        assert image is not None
        assert image['tag'] == '0.0.2'
