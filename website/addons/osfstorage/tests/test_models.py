from __future__ import unicode_literals

import mock
import unittest
from nose.tools import *  # noqa

from tests.factories import ProjectFactory

from website.addons.osfstorage.tests import factories
from website.addons.osfstorage.tests.utils import StorageTestCase

import datetime

from modularodm import exceptions as modm_errors


from website.files import models
from website.addons.osfstorage import utils
from website.addons.osfstorage import settings


class TestOsfstorageFileNode(StorageTestCase):

    def test_root_node_exists(self):
        assert_true(self.node_settings.root_node is not None)

    def test_root_node_has_no_parent(self):
        assert_true(self.node_settings.root_node.parent is None)

    def test_node_reference(self):
        assert_equal(self.project, self.node_settings.root_node.node)

    # def test_get_folder(self):
    #     file = models.OsfStorageFileNode(name='MOAR PYLONS', is_file=True, node=self.node)
    #     folder = models.OsfStorageFileNode(name='MOAR PYLONS', is_file=False, node=self.node)

    #     _id = folder._id

    #     file.save()
    #     folder.save()

    #     assert_equal(folder, models.OsfStorageFileNode.get_folder(_id, self.node_settings))

    # def test_get_file(self):
    #     file = models.OsfStorageFileNode(name='MOAR PYLONS', is_file=True, node=self.node)
    #     folder = models.OsfStorageFileNode(name='MOAR PYLONS', is_file=False, node=self.node)

    #     file.save()
    #     folder.save()

    #     _id = file._id

    #     assert_equal(file, models.OsfStorageFileNode.get_file(_id, self.node_settings))

    def test_serialize(self):
        file = models.OsfStorageFile(name='MOAR PYLONS', node=self.node_settings.owner)

        assert_equals(file.serialize(), {
            u'id': file._id,
            u'path': file.path,
            u'name': 'MOAR PYLONS',
            u'kind': 'file',
            u'version': 0,
            u'downloads': 0,
            u'size': None,
            u'modified': None,
            u'contentType': None,
            u'md5': None,
            u'sha256': None,
        })

        version = file.create_version(
            self.user,
            {
                'service': 'cloud',
                settings.WATERBUTLER_RESOURCE: 'osf',
                'object': '06d80e',
            }, {
                'size': 1234,
                'contentType': 'text/plain'
            })

        assert_equals(file.serialize(), {
            'id': file._id,
            'path': file.path,
            'name': 'MOAR PYLONS',
            'kind': 'file',
            'version': 1,
            'downloads': 0,
            'size': 1234,
            'modified': None,
            'contentType': 'text/plain',
            'md5': None,
            'sha256': None,
        })

        date = datetime.datetime.now()
        version.update_metadata({
            'modified': date.isoformat()
        })

        assert_equals(file.serialize(), {
            'id': file._id,
            'path': file.path,
            'name': 'MOAR PYLONS',
            'kind': 'file',
            'version': 1,
            'downloads': 0,
            'size': 1234,
            'modified': date.isoformat(),
            'contentType': 'text/plain',
            'md5': None,
            'sha256': None,
        })

    def test_get_child_by_name(self):
        child = self.node_settings.get_root().append_file('Test')
        assert_equal(child, self.node_settings.get_root().find_child_by_name('Test'))

    def test_root_node_path(self):
        assert_equal(self.node_settings.get_root().name, '')

    def test_folder_path(self):
        path = '/{}/'.format(self.node_settings.root_node._id)

        assert_equal(self.node_settings.get_root().path, path)

    def test_file_path(self):
        file = models.OsfStorageFileNode(name='MOAR PYLONS', is_file=True, node=self.node)
        file.save()
        assert_equal(file.name, 'MOAR PYLONS')
        assert_equal(file.path, '/{}'.format(file._id))

    def test_append_folder(self):
        child = self.node_settings.get_root().append_folder('Test')
        children = self.node_settings.get_root().children

        assert_equal(child.kind, 'folder')
        assert_equal([child], list(children))

    def test_append_file(self):
        child = self.node_settings.get_root().append_file('Test')
        children = self.node_settings.get_root().children

        assert_equal(child.kind, 'file')
        assert_equal([child], list(children))

    def test_append_to_file(self):
        child = self.node_settings.get_root().append_file('Test')
        with assert_raises(AttributeError):
            child.append_file('Cant')

    def test_children(self):
        assert_equals([
            self.node_settings.get_root().append_file('Foo{}Bar'.format(x))
            for x in xrange(100)
        ], list(self.node_settings.get_root().children))

    def test_download_count_file_defaults(self):
        child = self.node_settings.get_root().append_file('Test')
        assert_equals(child.get_download_count(), 0)

    @mock.patch('framework.analytics.session')
    def test_download_count_file(self, mock_session):
        mock_session.data = {}
        child = self.node_settings.get_root().append_file('Test')

        utils.update_analytics(self.project, child._id, 0)
        utils.update_analytics(self.project, child._id, 1)
        utils.update_analytics(self.project, child._id, 2)

        assert_equals(child.get_download_count(), 3)
        assert_equals(child.get_download_count(0), 1)
        assert_equals(child.get_download_count(1), 1)
        assert_equals(child.get_download_count(2), 1)

    @unittest.skip
    def test_create_version(self):
        pass

    @unittest.skip
    def test_update_version_metadata(self):
        pass

    def test_delete_folder(self):
        parent = self.node_settings.get_root().append_folder('Test')
        kids = []
        for x in range(10):
            kid = parent.append_file(str(x))
            kid.save()
            kids.append(kid)
        count = models.OsfStorageFileNode.find().count()
        tcount = models.TrashedFileNode.find().count()

        parent.delete()

        assert_is(models.OsfStorageFileNode.load(parent._id), None)
        assert_equals(count - 11, models.OsfStorageFileNode.find().count())
        assert_equals(tcount + 11, models.TrashedFileNode.find().count())

        for kid in kids:
            assert_is(
                models.OsfStorageFileNode.load(kid._id),
                None
            )

    def test_delete_file(self):
        child = self.node_settings.get_root().append_file('Test')
        child.delete()

        assert_is(models.OsfStorageFileNode.load(child._id), None)
        trashed = models.TrashedFileNode.load(child._id)
        child_storage = child.to_storage()
        trashed_storage = trashed.to_storage()
        trashed_storage['parent'] = trashed_storage['parent'][0]
        child_storage['materialized_path'] = child.materialized_path
        trashed_storage.pop('deleted_by')
        trashed_storage.pop('deleted_on')
        assert_equal(child_storage.pop('path'), '')
        assert_equal(trashed_storage.pop('path'), '/' + child._id)
        assert_equal(trashed_storage, child_storage)

    def test_materialized_path(self):
        child = self.node_settings.get_root().append_file('Test')
        assert_equals('/Test', child.materialized_path)

    def test_materialized_path_folder(self):
        child = self.node_settings.get_root().append_folder('Test')
        assert_equals('/Test/', child.materialized_path)

    def test_materialized_path_nested(self):
        child = self.node_settings.get_root().append_folder('Cloud').append_file('Carp')
        assert_equals('/Cloud/Carp', child.materialized_path)

    def test_copy(self):
        to_copy = self.node_settings.get_root().append_file('Carp')
        copy_to = self.node_settings.get_root().append_folder('Cloud')

        copied = to_copy.copy_under(copy_to)

        assert_not_equal(copied, to_copy)
        assert_equal(copied.parent, copy_to)
        assert_equal(to_copy.parent, self.node_settings.get_root())

    def test_move_nested(self):
        new_project = ProjectFactory()
        other_node_settings = new_project.get_addon('osfstorage')
        move_to = other_node_settings.get_root().append_folder('Cloud')

        to_move = self.node_settings.get_root().append_folder('Carp')
        child = to_move.append_file('A dee um')

        moved = to_move.move_under(move_to)
        child.reload()

        assert_equal(moved, to_move)
        assert_equal(new_project, to_move.node)
        assert_equal(new_project, move_to.node)
        assert_equal(new_project, child.node)

    def test_copy_rename(self):
        to_copy = self.node_settings.get_root().append_file('Carp')
        copy_to = self.node_settings.get_root().append_folder('Cloud')

        copied = to_copy.copy_under(copy_to, name='But')

        assert_equal(copied.name, 'But')
        assert_not_equal(copied, to_copy)
        assert_equal(to_copy.name, 'Carp')
        assert_equal(copied.parent, copy_to)
        assert_equal(to_copy.parent, self.node_settings.get_root())

    def test_move(self):
        to_move = self.node_settings.get_root().append_file('Carp')
        move_to = self.node_settings.get_root().append_folder('Cloud')

        moved = to_move.move_under(move_to)

        assert_equal(to_move, moved)
        assert_equal(moved.parent, move_to)

    def test_move_and_rename(self):
        to_move = self.node_settings.get_root().append_file('Carp')
        move_to = self.node_settings.get_root().append_folder('Cloud')

        moved = to_move.move_under(move_to, name='Tuna')

        assert_equal(to_move, moved)
        assert_equal(to_move.name, 'Tuna')
        assert_equal(moved.parent, move_to)

    @unittest.skip
    def test_move_folder(self):
        pass

    @unittest.skip
    def test_move_folder_and_rename(self):
        pass

    @unittest.skip
    def test_rename_folder(self):
        pass

    @unittest.skip
    def test_rename_file(self):
        pass

    @unittest.skip
    def test_move_across_nodes(self):
        pass

    @unittest.skip
    def test_move_folder_across_nodes(self):
        pass

    @unittest.skip
    def test_copy_across_nodes(self):
        pass

    @unittest.skip
    def test_copy_folder_across_nodes(self):
        pass

class TestNodeSettingsModel(StorageTestCase):

    def test_fields(self):
        assert_true(self.node_settings._id)
        assert_is(self.node_settings.has_auth, True)
        assert_is(self.node_settings.complete, True)

    def test_after_fork_copies_versions(self):
        num_versions = 5
        path = 'jazz/dreamers-ball.mp3'

        record = self.node_settings.get_root().append_file(path)

        for _ in range(num_versions):
            version = factories.FileVersionFactory()
            record.versions.append(version)
        record.save()

        fork = self.project.fork_node(self.auth_obj)
        fork_node_settings = fork.get_addon('osfstorage')
        fork_node_settings.reload()

        cloned_record = fork_node_settings.get_root().find_child_by_name(path)
        assert_equal(cloned_record.versions, record.versions)
        assert_true(fork_node_settings.root_node)


class TestOsfStorageFileVersion(StorageTestCase):

    def setUp(self):
        super(TestOsfStorageFileVersion, self).setUp()
        self.user = factories.AuthUserFactory()
        self.mock_date = datetime.datetime(1991, 10, 31)

    def test_fields(self):
        version = factories.FileVersionFactory(
            size=1024,
            content_type='application/json',
            date_modified=datetime.datetime.now(),
        )
        retrieved = models.FileVersion.load(version._id)
        assert_true(retrieved.creator)
        assert_true(retrieved.location)
        assert_true(retrieved.size)
        assert_is(retrieved.identifier, 0)
        assert_true(retrieved.content_type)
        assert_true(retrieved.date_modified)

    def test_is_duplicate_true(self):
        version1 = factories.FileVersionFactory()
        version2 = factories.FileVersionFactory()
        assert_true(version1.is_duplicate(version2))
        assert_true(version2.is_duplicate(version1))

    def test_is_duplicate_false(self):
        version1 = factories.FileVersionFactory(
            location={
                'service': 'cloud',
                settings.WATERBUTLER_RESOURCE: 'osf',
                'object': 'd077f2',
            },
        )
        version2 = factories.FileVersionFactory(
            location={
                'service': 'cloud',
                settings.WATERBUTLER_RESOURCE: 'osf',
                'object': '06d80e',
            },
        )
        assert_false(version1.is_duplicate(version2))
        assert_false(version2.is_duplicate(version1))

    def test_validate_location(self):
        version = factories.FileVersionFactory.build(location={})
        with assert_raises(modm_errors.ValidationValueError):
            version.save()
        version.location = {
            'service': 'cloud',
            settings.WATERBUTLER_RESOURCE: 'osf',
            'object': 'object',
        }
        version.save()

    def test_update_metadata(self):
        version = factories.FileVersionFactory()
        version.update_metadata({'archive': 'glacier', 'size': 123, 'modified': 'Mon, 16 Feb 2015 18:45:34 GMT'})
        version.reload()
        assert_in('archive', version.metadata)
        assert_equal(version.metadata['archive'], 'glacier')

    def test_matching_archive(self):
        version = factories.FileVersionFactory(
            location={
                'service': 'cloud',
                settings.WATERBUTLER_RESOURCE: 'osf',
                'object': 'd077f2',
            },
            metadata={'sha256': 'existing'}
        )
        factories.FileVersionFactory(
            location={
                'service': 'cloud',
                settings.WATERBUTLER_RESOURCE: 'osf',
                'object': '06d80e',
            },
            metadata={
                'sha256': 'existing',
                'vault': 'the cloud',
                'archive': 'erchiv'
            }
        )

        assert_is(version._find_matching_archive(), True)
        assert_is_not(version.archive, None)

        assert_equal(version.metadata['vault'], 'the cloud')
        assert_equal(version.metadata['archive'], 'erchiv')

    def test_archive_exits(self):
        node_addon = self.project.get_addon('osfstorage')
        fnode = node_addon.get_root().append_file('MyCoolTestFile')
        version = fnode.create_version(
            self.user,
            {
                'service': 'cloud',
                settings.WATERBUTLER_RESOURCE: 'osf',
                'object': '06d80e',
            }, {
                'sha256': 'existing',
                'vault': 'the cloud',
                'archive': 'erchiv'
            })

        assert_equal(version.archive, 'erchiv')

        version2 = fnode.create_version(
            self.user,
            {
                'service': 'cloud',
                settings.WATERBUTLER_RESOURCE: 'osf',
                'object': '07d80a',
            }, {
                'sha256': 'existing',
            })

        assert_equal(version2.archive, 'erchiv')

    def test_no_matching_archive(self):
        models.FileVersion.remove()
        assert_is(False, factories.FileVersionFactory(
            location={
                'service': 'cloud',
                settings.WATERBUTLER_RESOURCE: 'osf',
                'object': 'd077f2',
            },
            metadata={'sha256': 'existing'}
        )._find_matching_archive())
