from rest_framework import serializers as ser
from rest_framework import exceptions

from framework.auth.core import Auth

from website.models import Node, User
from website.util import permissions as osf_permissions

from api.base.utils import get_object_or_error
from api.base.serializers import JSONAPISerializer, Link, WaterbutlerLink, LinksField, JSONAPIHyperlinkedIdentityField


class NodeTagField(ser.Field):

    def to_representation(self, obj):
        if obj is not None:
            return obj._id
        return None

    def to_internal_value(self, data):
        return data


class NodeSerializer(JSONAPISerializer):
    # TODO: If we have to redo this implementation in any of the other serializers, subclass ChoiceField and make it
    # handle blank choices properly. Currently DRF ChoiceFields ignore blank options, which is incorrect in this
    # instance
    category_choices = Node.CATEGORY_MAP.keys()
    category_choices_string = ', '.join(["'{}'".format(choice) for choice in category_choices])
    filterable_fields = frozenset(['title', 'description', 'public'])

    id = ser.CharField(read_only=True, source='_id', label='ID')
    title = ser.CharField(required=True)
    description = ser.CharField(required=False, allow_blank=True, allow_null=True)
    category = ser.ChoiceField(choices=category_choices, help_text="Choices: " + category_choices_string)
    date_created = ser.DateTimeField(read_only=True)
    date_modified = ser.DateTimeField(read_only=True)
    tags = ser.ListField(child=NodeTagField(), required=False)
    registration = ser.BooleanField(read_only=True, source='is_registration')
    collection = ser.BooleanField(read_only=True, source='is_folder')
    dashboard = ser.BooleanField(read_only=True, source='is_dashboard')

    links = LinksField({'html': 'get_absolute_url'})
    # TODO: When we have osf_permissions.ADMIN permissions, make this writable for admins
    public = ser.BooleanField(source='is_public', read_only=True,
                              help_text='Nodes that are made public will give read-only access '
                                                            'to everyone. Private nodes require explicit read '
                                                            'permission. Write and admin access are the same for '
                                                            'public and private nodes. Administrators on a parent '
                                                            'node have implicit read permissions for all child nodes',
                              )

    children = JSONAPIHyperlinkedIdentityField(view_name='nodes:node-children', lookup_field='pk', link_type='related',
                                                lookup_url_kwarg='node_id', meta={'count': 'get_node_count'})

    contributors = JSONAPIHyperlinkedIdentityField(view_name='nodes:node-contributors', lookup_field='pk', link_type='related',
                                                    lookup_url_kwarg='node_id', meta={'count': 'get_contrib_count'})

    files = JSONAPIHyperlinkedIdentityField(view_name='nodes:node-files', lookup_field='pk', lookup_url_kwarg='node_id',
                                             link_type='related')

    node_links = JSONAPIHyperlinkedIdentityField(view_name='nodes:node-pointers', lookup_field='pk', link_type='related',
                                                  lookup_url_kwarg='node_id', meta={'count': 'get_pointers_count'})

    parent = JSONAPIHyperlinkedIdentityField(view_name='nodes:node-detail', lookup_field='parent_id', link_type='self',
                                              lookup_url_kwarg='node_id')

    registrations = JSONAPIHyperlinkedIdentityField(view_name='nodes:node-registrations', lookup_field='pk', link_type='related',
                                                     lookup_url_kwarg='node_id', meta={'count': 'get_registration_count'})

    class Meta:
        type_ = 'nodes'

    def get_absolute_url(self, obj):
        return obj.absolute_url

    # TODO: See if we can get the count filters into the filter rather than the serializer.

    def get_user_auth(self, request):
        user = request.user
        if user.is_anonymous():
            auth = Auth(None)
        else:
            auth = Auth(user)
        return auth

    def get_node_count(self, obj):
        auth = self.get_user_auth(self.context['request'])
        nodes = [node for node in obj.nodes if node.can_view(auth) and node.primary and not node.is_deleted]
        return len(nodes)

    def get_contrib_count(self, obj):
        return len(obj.contributors)

    def get_registration_count(self, obj):
        auth = self.get_user_auth(self.context['request'])
        registrations = [node for node in obj.node__registrations if node.can_view(auth)]
        return len(registrations)

    def get_pointers_count(self, obj):
        return len(obj.nodes_pointer)

    def create(self, validated_data):
        node = Node(**validated_data)
        node.save()
        return node

    def update(self, node, validated_data):
        """Update instance with the validated data. Requires
        the request to be in the serializer context.
        """
        assert isinstance(node, Node), 'node must be a Node'
        auth = self.get_user_auth(self.context['request'])
        tags = validated_data.get('tags')
        if tags:
            del validated_data['tags']
            current_tags = set(tags)
        else:
            current_tags = set()
        old_tags = set([tag._id for tag in node.tags])
        for new_tag in (current_tags - old_tags):
            node.add_tag(new_tag, auth=auth)
        for deleted_tag in (old_tags - current_tags):
            node.remove_tag(deleted_tag, auth=auth)
        node.update(validated_data, auth=auth)
        return node


class NodeContributorsSerializer(JSONAPISerializer):
    """ Separate from UserSerializer due to necessity to override almost every field as read only
    """
    filterable_fields = frozenset([
        'fullname',
        'given_name',
        'middle_name',
        'family_name',
        'id',
        'bibliographic',
        'permissions'
    ])
    id = ser.CharField(source='_id', label='ID')
    fullname = ser.CharField(read_only=True, help_text='Display name used in the general user interface')
    given_name = ser.CharField(read_only=True, help_text='For bibliographic citations')
    middle_name = ser.CharField(read_only=True, source='middle_names', help_text='For bibliographic citations')
    family_name = ser.CharField(read_only=True, help_text='For bibliographic citations')
    suffix = ser.CharField(read_only=True, help_text='For bibliographic citations')
    date_registered = ser.DateTimeField(read_only=True)
    gravatar_url = ser.CharField(read_only=True, help_text='URL for the icon used to identify the user. '
                                                           'Relies on http://gravatar.com ')
    social_accounts = ser.DictField(read_only=True, source='social',
                                    help_text='A dictionary of various social media account dentifiers including '
                                              'an array of user-defined URLs')
    bibliographic = ser.BooleanField(help_text='Whether the user will be included in citations for this node or not.  '
                                               'Required due to issues with field defaulting to false.')

    permission = ser.ChoiceField(choices=osf_permissions.PERMISSIONS, required=False, allow_null=True,
                                 help_text='Highest permission the user has.  Blank input defaults write permission if '
                                           'user is being added and to current permission if user is being edited.')

    links = LinksField({'html': 'absolute_url'})
    nodes = JSONAPIHyperlinkedIdentityField(view_name='users:user-nodes', lookup_field='pk', lookup_url_kwarg='user_id',
                                             link_type='related')
    detail = JSONAPIHyperlinkedIdentityField(view_name='users:user-detail', lookup_field='pk', lookup_url_kwarg='user_id', link_type='related')

    class Meta:
        type_ = 'users'

    def absolute_url(self, obj):
        return obj.absolute_url

    def create(self, validated_data):
        auth = Auth(self.context['request'].user)
        node = self.context['view'].get_node()
        contributor = get_object_or_error(User, validated_data['_id'], display_name='user')
        # Node object checks for contributor existence but can still change permissions anyway
        if contributor in node.contributors:
            raise exceptions.ValidationError('{} is already a contributor'.format(contributor.username))

        bibliographic = validated_data['bibliographic']
        permissions = osf_permissions.expand_permissions(validated_data.get('permission')) or osf_permissions.DEFAULT_CONTRIBUTOR_PERMISSIONS
        node.add_contributor(contributor=contributor, auth=auth, visible=bibliographic, permissions=permissions, save=True)
        contributor.permission = osf_permissions.reduce_permissions(node.get_permissions(contributor))
        contributor.bibliographic = node.get_visible(contributor)
        contributor.node_id = node._id
        return contributor


class NodeContributorDetailSerializer(NodeContributorsSerializer):
    """ Overrides node contributor serializer to make id read only and add additional methods
    """
    id = ser.CharField(read_only=True, source='_id', label='ID')

    def update(self, instance, validated_data):
        contributor = instance
        auth = Auth(self.context['request'].user)
        node = self.context['view'].get_node()

        visible = validated_data.get('bibliographic')
        permission = validated_data.get('permission')
        self._check_permissions(node, permission, contributor, auth)
        try:
            node.update_contributor(contributor, permission, visible, auth, save=True)
        except ValueError as e:
            raise exceptions.ValidationError(e)
        contributor.permission = osf_permissions.reduce_permissions(node.get_permissions(contributor))
        contributor.bibliographic = node.get_visible(contributor)
        contributor.node_id = node._id
        return contributor

    def _check_permissions(self, node, permission, contributor, auth):
        """ Check contributor permissions. Checks to make sure unique admin is
        removing own admin privilege. Based on the ContributorDetailPermissions
        permissions class, the current user must be an admin.
        """
        assert node.has_permission(auth.user, osf_permissions.ADMIN), "Only admins can modify contributor permissions"
        permissions = osf_permissions.expand_permissions(permission) or osf_permissions.DEFAULT_CONTRIBUTOR_PERMISSIONS
        if not self.has_multiple_admins(node):
            # has only one admin
            admin = self._get_admins(node)[0]
            if admin == contributor and osf_permissions.ADMIN not in permissions:
                raise exceptions.ValidationError('{} is the only admin.'.format(contributor.username))

    def _get_admins(self, node):
        return [
            contributor for contributor in node.contributors
            if node.has_permission(contributor, osf_permissions.ADMIN)
        ]

    # Get the list of admins for just this node
    def has_multiple_admins(self, node):
        return len(self._get_admins(node)) >= 2

class NodeLinksSerializer(JSONAPISerializer):

    id = ser.CharField(read_only=True, source='_id', label='ID')
    target_node_id = ser.CharField(source='node._id', help_text='The ID of the node that this Node Link points to')
    title = ser.CharField(read_only=True, source='node.title', help_text='The title of the node that this Node Link '
                                                                         'points to')

    class Meta:
        type_ = 'node_links'

    links = LinksField({
        'html': 'get_absolute_url',
    })

    def get_absolute_url(self, obj):
        pointer_node = Node.load(obj.node._id)
        return pointer_node.absolute_url

    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        auth = Auth(user)
        node = self.context['view'].get_node()
        pointer_node = Node.load(validated_data['node']['_id'])
        if not pointer_node:
            raise exceptions.NotFound('Node not found.')
        try:
            pointer = node.add_pointer(pointer_node, auth, save=True)
            return pointer
        except ValueError:
            raise exceptions.ValidationError('Node link to node {} already in list'.format(pointer_node._id))

    def update(self, instance, validated_data):
        pass


class NodeFilesSerializer(JSONAPISerializer):

    id = ser.SerializerMethodField(label='ID')
    provider = ser.CharField(read_only=True)
    path = ser.CharField(read_only=True)
    item_type = ser.CharField(read_only=True)
    name = ser.CharField(read_only=True)
    metadata = ser.DictField(read_only=True)

    class Meta:
        type_ = 'files'

    links = LinksField({
        'self': WaterbutlerLink(kwargs={'node_id': '<node_id>'}),
        'related': {
            'href': Link('nodes:node-files', kwargs={'node_id': '<node_id>'},
                    query_kwargs={'path': '<path>', 'provider': '<provider>'}),
            'meta': {'self_methods': 'valid_self_link_methods'}
        }
    })

    @staticmethod
    def get_id(obj):
        ret = obj['provider'] + obj['path']
        return ret

    @staticmethod
    def valid_self_link_methods(obj):
        return obj['valid_self_link_methods']

    def create(self, validated_data):
        # TODO
        pass

    def update(self, instance, validated_data):
        # TODO
        pass
