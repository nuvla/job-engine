import unittest

from nuvla.connector.registry import image_str_to_dict, image_dict_to_str


class TestRegistry(unittest.TestCase):

    def test_image_str_to_dict(self):

        image = image_str_to_dict('registry.com/repo:1.2.3')
        assert image['registry'] == 'registry.com'
        assert image['repository'] == 'repo'
        assert image['tag'] == '1.2.3'

        image = image_str_to_dict('registry.com/repo/name:1.2.3')
        assert image['registry'] == 'registry.com'
        assert image['repository'] == 'repo/name'
        assert image['tag'] == '1.2.3'

        image = image_str_to_dict('registry.com/repo/name')
        assert image['registry'] == 'registry.com'
        assert image['repository'] == 'repo/name'
        assert image['tag'] == 'latest'

        image = image_str_to_dict('repo')
        assert image['registry'] == ''
        assert image['repository'] == 'repo'
        assert image['tag'] == 'latest'

        image = image_str_to_dict('repo/name')
        assert image['registry'] == ''
        assert image['repository'] == 'repo/name'
        assert image['tag'] == 'latest'

        image = image_str_to_dict('repo:1.2.3')
        assert image['registry'] == ''
        assert image['repository'] == 'repo'
        assert image['tag'] == '1.2.3'

        image = image_str_to_dict('repo/name:1.2.3')
        assert image['registry'] == ''
        assert image['repository'] == 'repo/name'
        assert image['tag'] == '1.2.3'

    def test_image_dict_to_str(self):
        # FIXME: remove when 'image-name' is removed from component definition
        image = image_dict_to_str({'registry': '',
                                   'repository': 'repo',
                                   'image-name': 'name',
                                   'tag': ''})
        assert image == 'repo/name'

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
