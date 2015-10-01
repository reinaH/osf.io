# -*- coding: utf-8 -*-
import os
import logging

from modularodm import fields

from framework.auth import Auth
from website.addons.base import exceptions
from website.addons.base import AddonUserSettingsBase, AddonNodeSettingsBase
from website.addons.base import StorageAddonBase

from website.addons.dropbox.utils import DropboxNodeLogger

logger = logging.getLogger(__name__)


class DropboxUserSettings(AddonUserSettingsBase):
    """Stores user-specific dropbox information, including the Oauth access
    token.
    """

    dropbox_id = fields.StringField(required=False)
    access_token = fields.StringField(required=False)
    dropbox_info = fields.DictionaryField(required=False)

    # TODO(sloria): The `user` param in unnecessary for AddonUserSettings
    def to_json(self, user=None):
        """Return a dictionary representation of the user settings.
        The dictionary keys and values will be available as variables in
        dropbox_user_settings.mako.
        """
        output = super(DropboxUserSettings, self).to_json(self.owner)
        output['has_auth'] = self.has_auth
        return output

    @property
    def has_auth(self):
        return bool(self.access_token)

    def delete(self, save=True):
        self.clear()
        super(DropboxUserSettings, self).delete(save)

    def clear(self):
        """Clear settings and deauthorize any associated nodes."""
        self.dropbox_id = None
        self.access_token = None
        for node_settings in self.dropboxnodesettings__authorized:
            node_settings.deauthorize(Auth(self.owner))
            node_settings.save()
        return self

    def __repr__(self):
        return u'<DropboxUserSettings(user={self.owner.username!r})>'.format(self=self)

class DropboxNodeSettings(StorageAddonBase, AddonNodeSettingsBase):
    user_settings = fields.ForeignField(
        'dropboxusersettings', backref='authorized'
    )

    folder = fields.StringField(default=None)

    #: Information saved at the time of registration
    #: Note: This is unused right now
    registration_data = fields.DictionaryField()

    @property
    def folder_name(self):
        return os.path.split(self.folder)[1]
    @property
    def display_name(self):
        return '{0}: {1}'.format(self.config.full_name, self.folder)

    @property
    def complete(self):
        return self.has_auth and self.folder is not None

    @property
    def has_auth(self):
        """Whether an access token is associated with this node."""
        return bool(self.user_settings and self.user_settings.has_auth)

    def set_folder(self, folder, auth):
        self.folder = folder
        # Add log to node
        nodelogger = DropboxNodeLogger(node=self.owner, auth=auth)
        nodelogger.log(action="folder_selected", save=True)

    def set_user_auth(self, user_settings):
        """Import a user's Dropbox authentication and create a NodeLog.

        :param DropboxUserSettings user_settings: The user settings to link.
        """
        self.user_settings = user_settings
        nodelogger = DropboxNodeLogger(node=self.owner, auth=Auth(user_settings.owner))
        nodelogger.log(action="node_authorized", save=True)

    # TODO: Is this used? If not, remove this and perhaps remove the 'deleted' field
    def delete(self, save=True):
        self.deauthorize(add_log=False)
        super(DropboxNodeSettings, self).delete(save)

    def deauthorize(self, auth=None, add_log=True):
        """Remove user authorization from this node and log the event."""
        node = self.owner
        folder = self.folder

        self.folder = None
        self.user_settings = None

        if add_log:
            extra = {'folder': folder}
            nodelogger = DropboxNodeLogger(node=node, auth=auth)
            nodelogger.log(action="node_deauthorized", extra=extra, save=True)

    def serialize_waterbutler_credentials(self):
        if not self.has_auth:
            raise exceptions.AddonError('Addon is not authorized')
        return {'token': self.user_settings.access_token}

    def serialize_waterbutler_settings(self):
        if not self.folder:
            raise exceptions.AddonError('Folder is not configured')
        return {'folder': self.folder}

    def create_waterbutler_log(self, auth, action, metadata):
        url = self.owner.web_url_for('addon_view_or_download_file', path=metadata['path'].strip('/'), provider='dropbox')
        self.owner.add_log(
            'dropbox_{0}'.format(action),
            auth=auth,
            params={
                'project': self.owner.parent_id,
                'node': self.owner._id,
                'path': metadata['path'],
                'folder': self.folder,
                'urls': {
                    'view': url,
                    'download': url + '?action=download'
                },
            },
        )

    def __repr__(self):
        return u'<DropboxNodeSettings(node_id={self.owner._primary_key!r})>'.format(self=self)

    ##### Callback overrides #####

    def before_register_message(self, node, user):
        """Return warning text to display if user auth will be copied to a
        registration.
        """
        category = node.project_or_component
        if self.user_settings and self.user_settings.has_auth:
            return (
                u'The contents of Dropbox add-ons cannot be registered at this time; '
                u'the Dropbox folder linked to this {category} will not be included '
                u'as part of this registration.'
            ).format(**locals())

    # backwards compatibility
    before_register = before_register_message

    def before_remove_contributor_message(self, node, removed):
        """Return warning text to display if removed contributor is the user
        who authorized the Dropbox addon
        """
        if self.user_settings and self.user_settings.owner == removed:
            category = node.project_or_component
            name = removed.fullname
            return (u'The Dropbox add-on for this {category} is authenticated by {name}. '
                    'Removing this user will also remove write access to Dropbox '
                    'unless another contributor re-authenticates the add-on.'
                    ).format(**locals())

    # backwards compatibility
    before_remove_contributor = before_remove_contributor_message

    # Note: Registering Dropbox content is disabled for now; leaving this code
    # here in case we enable registrations later on.
    # @jmcarp
    # def after_register(self, node, registration, user, save=True):
    #     """After registering a node, copy the user settings and save the
    #     chosen folder.
    #
    #     :return: A tuple of the form (cloned_settings, message)
    #     """
    #     clone, message = super(DropboxNodeSettings, self).after_register(
    #         node, registration, user, save=False
    #     )
    #     # Copy user_settings and add registration data
    #     if self.has_auth and self.folder is not None:
    #         clone.user_settings = self.user_settings
    #         clone.registration_data['folder'] = self.folder
    #     if save:
    #         clone.save()
    #     return clone, message

    def after_fork(self, node, fork, user, save=True):
        """After forking, copy user settings if the user is the one who authorized
        the addon.

        :return: A tuple of the form (cloned_settings, message)
        """
        clone, _ = super(DropboxNodeSettings, self).after_fork(
            node=node, fork=fork, user=user, save=False
        )

        if self.user_settings and self.user_settings.owner == user:
            clone.user_settings = self.user_settings
            message = (
                'Dropbox authorization copied to forked {cat}.'
            ).format(
                cat=fork.project_or_component
            )
        else:
            message = (
                u'Dropbox authorization not copied to forked {cat}. You may '
                'authorize this fork on the <u><a href="{url}">Settings</a></u> '
                'page.'
            ).format(
                url=fork.web_url_for('node_setting'),
                cat=fork.project_or_component
            )
        if save:
            clone.save()
        return clone, message

    def after_remove_contributor(self, node, removed, auth=None):
        """If the removed contributor was the user who authorized the Dropbox
        addon, remove the auth credentials from this node.
        Return the message text that will be displayed to the user.
        """
        if self.user_settings and self.user_settings.owner == removed:
            self.user_settings = None
            self.save()

            message = (
                u'Because the Dropbox add-on for {category} "{title}" was authenticated '
                u'by {user}, authentication information has been deleted.'
            ).format(
                category=node.category_display,
                title=node.title,
                user=removed.fullname
            )

            if not auth or auth.user != removed:
                url = node.web_url_for('node_setting')
                message += (
                    u' You can re-authenticate on the <u><a href="{url}">Settings</a></u> page.'
                ).format(url=url)
            #
            return message

    def after_delete(self, node, user):
        self.deauthorize(Auth(user=user), add_log=True)
        self.save()
