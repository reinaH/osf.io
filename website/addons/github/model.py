"""

"""

import os
import json
import urlparse

from github3 import GitHubError

from framework import fields

from website import settings
from website.addons.base import AddonUserSettingsBase, AddonNodeSettingsBase
from website.addons.base import GuidFile
from website.addons.base import AddonError

from . import settings as github_settings
from .api import GitHub

hook_domain = github_settings.HOOK_DOMAIN or settings.DOMAIN

class GithubGuidFile(GuidFile):

    path = fields.StringField(index=True)

    @property
    def file_url(self):
        if self.path is None:
            raise ValueError('Path field must be defined.')
        return os.path.join('github', 'file', self.path)

class AddonGitHubUserSettings(AddonUserSettingsBase):

    github_user = fields.StringField()

    oauth_state = fields.StringField()
    oauth_access_token = fields.StringField()
    oauth_token_type = fields.StringField()

    @property
    def has_auth(self):
        return self.oauth_access_token is not None

    def to_json(self, user):
        rv = super(AddonGitHubUserSettings, self).to_json(user)
        rv.update({
            'authorized': self.has_auth,
            'authorized_github_user': self.github_user if self.github_user else '',
            'show_submit': False,
        })
        return rv

    def revoke_token(self):

        connection = GitHub.from_settings(self)
        try:
            connection.revoke_token()
        except GitHubError as error:
            if error.code == 401:
                return (
                    'Your GitHub credentials were removed from the OSF, but we '
                    'were unable to revoke your access token from GitHub. Your '
                    'GitHub credentials may no longer be valid.'
                )
            else:
                raise

    def clear_auth(self):

        self.revoke_token()

        self.oauth_access_token = None
        self.oauth_token_type = None
        self.save()

    def delete(self, save=True):
        super(AddonGitHubUserSettings, self).delete()
        self.clear_auth()
        for node_settings in self.addongithubnodesettings__authorized:
            node_settings.delete(save=False)
            node_settings.user_settings = None
            node_settings.save()

class AddonGitHubNodeSettings(AddonNodeSettingsBase):

    user = fields.StringField()
    repo = fields.StringField()
    hook_id = fields.StringField()

    user_settings = fields.ForeignField(
        'addongithubusersettings', backref='authorized'
    )

    registration_data = fields.DictionaryField()

    @property
    def repo_url(self):
        if self.user and self.repo:
            return 'https://github.com/{0}/{1}/'.format(
                self.user, self.repo
            )

    @property
    def short_url(self):
        if self.user and self.repo:
            return '/'.join([self.user, self.repo])

    @property
    def complete(self):
        return (
            self.user and self.repo and
            self.user_settings and self.user_settings.has_auth
        )

    def to_json(self, user):
        rv = super(AddonGitHubNodeSettings, self).to_json(user)
        user_settings = user.get_addon('github')
        rv.update({
            'user_has_auth': user_settings and user_settings.has_auth,
        })
        if self.user_settings and self.user_settings.has_auth:
            owner = self.user_settings.owner
            connection = GitHub.from_settings(user_settings)
            repo_names = [
                '{0} / {1}'.format(repo.owner.login, repo.name)
                for repo in connection.repos()
            ]
            rv.update({
                'node_has_auth': True,
                'github_user': self.user or '',
                'github_repo': self.repo or '',
                'github_repo_full_name': '{0} / {1}'.format(self.user, self.repo),
                'repo_names': repo_names,
                'auth_osf_name': owner.fullname,
                'auth_osf_url': owner.url,
                'auth_osf_id': owner._id,
                'github_user_name': self.user_settings.github_user,
                'github_user_url': 'https://githubcom/{0}'.format(self.user_settings.github_user),
                'is_owner': owner == user,
            })
        return rv

    #############
    # Callbacks #
    #############

    def before_page_load(self, node, user):
        """

        :param Node node:
        :param User user:
        :return str: Alert message

        """
        messages = []

        # Quit if not contributor
        if not node.is_contributor(user):
            return messages

        # Quit if not configured
        if self.user is None or self.repo is None:
            return messages

        # Quit if no user authorization
        if self.user_settings is None:
            return messages

        connect = GitHub.from_settings(self.user_settings)
        repo = connect.repo(self.user, self.repo)

        # Quit if request failed
        if repo is None:
            return

        node_permissions = 'public' if node.is_public else 'private'
        repo_permissions = 'private' if repo.private else 'public'
        if repo_permissions != node_permissions:
            message = (
                'Warnings: This OSF {category} is {node_perm}, but the GitHub '
                'repo {user} / {repo} is {repo_perm}.'.format(
                    category=node.project_or_component,
                    node_perm=node_permissions,
                    repo_perm=repo_permissions,
                    user=self.user,
                    repo=self.repo,
                )
            )
            if repo_permissions == 'private':
                message += (
                    ' Users can view the contents of this private GitHub '
                    'repository through this public project.'
                )
            else:
                message += (
                    ' The files in this GitHub repo can be viewed on GitHub '
                    '<a href="https://github.com/{user}/{repo}/">here</a>.'
                ).format(
                    user=self.user,
                    repo=self.repo,
                )
            messages.append(message)
            return messages

    # TODO: Rename to before_remove_contributor_message
    def before_remove_contributor(self, node, removed):
        """

        :param Node node:
        :param User removed:
        :return str: Alert message

        """
        if self.user_settings and self.user_settings.owner == removed:
            return (
                'The GitHub add-on for this {category} is authenticated '
                'by {user}. Removing this user will also remove write access '
                'to GitHub unless another contributor re-authenticates. You '
                'can download the contents of this repository before removing '
                'this contributor <a href="{url}">here</a>.'
            ).format(
                category=node.project_or_component,
                user=removed.fullname,
                url=node.api_url + 'github/tarball/'
            )

    def after_remove_contributor(self, node, removed):
        """

        :param Node node:
        :param User removed:
        :return str: Alert message

        """
        if self.user_settings and self.user_settings.owner == removed:

            # Delete OAuth tokens
            self.user_settings = None
            self.save()

            #
            return (
                'Because the GitHub add-on for this project was authenticated '
                'by {user}, authentication information has been deleted. You '
                'can re-authenticate on the <a href="{url}settings/">'
                'Settings</a> page.'.format(
                    user=removed.fullname,
                    url=node.url,
                )
            )

    def after_set_permissions(self, node, permissions):
        """

        :param Node node:
        :param str permissions:
        :return str: Alert message

        """
        if not github_settings.SET_PRIVACY:
            return

        connect = GitHub.from_settings(self.user_settings)

        data = connect.set_privacy(
            self.user, self.repo, permissions == 'private'
        )
        if data is None or 'errors' in data:
            repo = connect.repo(self.user, self.repo)
            if repo is not None:
                current_privacy = 'private' if repo.private else 'public'
            else:
                current_privacy = 'unknown'
            return (
                'Could not set privacy for repo {user}::{repo}. '
                'Current privacy status is {perm}.'.format(
                    user=self.user,
                    repo=self.repo,
                    perm=current_privacy,
                )
            )

        return (
            'GitHub repo {user}::{repo} made {perm}.'.format(
                user=self.user,
                repo=self.repo,
                perm=permissions,
            )
        )

    def before_fork(self, node, user):
        """

        :param Node node:
        :param User user:
        :return str: Alert message

        """
        if self.user_settings and self.user_settings.owner == user:
            return (
                'Because you have authenticated the GitHub add-on for this '
                '{cat}, forking it will also transfer your authorization to '
                'the forked {cat}.'
            ).format(
                cat=node.project_or_component,
            )
        return (
            'Because this GitHub add-on has been authenticated by a different '
            'user, forking it will not transfer authentication to the forked '
            '{cat}.'
        ).format(
            cat=node.project_or_component,
        )

    def after_fork(self, node, fork, user, save=True):
        """

        :param Node node: Original node
        :param Node fork: Forked node
        :param User user: User creating fork
        :param bool save: Save settings after callback
        :return tuple: Tuple of cloned settings and alert message

        """
        clone, _ = super(AddonGitHubNodeSettings, self).after_fork(
            node, fork, user, save=False
        )

        # Copy authentication if authenticated by forking user
        if self.user_settings and self.user_settings.owner == user:
            clone.user_settings = self.user_settings
            message = (
                'GitHub authorization copied to forked {cat}.'
            ).format(
                cat=fork.project_or_component,
            )
        else:
            message = (
                'GitHub authorization not copied to forked {cat}. You may '
                'authorize this fork on the <a href={url}>Settings</a> '
                'page.'
            ).format(
                cat=fork.project_or_component,
                url=fork.url + 'settings/'
            )

        if save:
            clone.save()

        return clone, message

    def before_register(self, node, user):
        """

        :param Node node:
        :param User user:
        :return str: Alert message

        """
        if self.user_settings:
            return (
                'Registering {cat} "{title}" will copy the authentication for its '
                'GitHub add-on to the registered {cat}.'
            ).format(
                cat=node.project_or_component,
                title=node.title,
            )

    def after_register(self, node, registration, user, save=True):
        """

        :param Node node: Original node
        :param Node registration: Registered node
        :param User user: User creating registration
        :param bool save: Save settings after callback
        :return tuple: Tuple of cloned settings and alert message

        """
        clone, message = super(AddonGitHubNodeSettings, self).after_register(
            node, registration, user, save=False
        )

        # Copy foreign fields from current add-on
        clone.user_settings = self.user_settings

        # Store current branch data
        if self.user and self.repo:
            connect = GitHub.from_settings(self.user_settings)
            branches = [branch.to_json() for branch in connect.branches(self.user, self.repo)]
            if not branches:
                raise AddonError('Could not fetch repo branches.')
            clone.registration_data['branches'] = branches

        if save:
            clone.save()

        return clone, message

    #########
    # Hooks #
    #########
    # TODO Should Events be added here?
    def add_hook(self, save=True):

        if self.user_settings:
            connect = GitHub.from_settings(self.user_settings)
            hook = connect.add_hook(
                self.user, self.repo,
                'web',
                {
                    'url': urlparse.urljoin(
                        hook_domain,
                        os.path.join(
                            self.owner.api_url, 'github', 'hook/'
                        )
                    )
                }
            )

            if hook:
                self.hook_id = hook.id
                if save:
                    self.save()

    def delete_hook(self, save=True):
        """

        :return bool: Hook was deleted

        """
        if self.user_settings and self.hook_id:
            connection = GitHub.from_settings(self.user_settings)
            response = connection.delete_hook(self.user, self.repo, self.hook_id)
            if response:
                self.hook_id = None
                if save:
                    self.save()
                return True
        return False
