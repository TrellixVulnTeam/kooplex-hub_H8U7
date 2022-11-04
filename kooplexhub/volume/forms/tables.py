from django.utils.html import format_html
import django_tables2 as tables

from hub.templatetags.extras import render_user as ru
from ..models import UserVolumeBinding
from hub.models import Profile

class TableVolumeShare(tables.Table):
    user = tables.Column(verbose_name = "Collaborators", order_by = ('user__first_name', 'user__last_name'), orderable = False)

    class Meta:
        model = UserVolumeBinding
        fields = ('user',)
        attrs = {
                 "class": "table table-bordered",
                 "thead": { "class": "thead-dark table-sm" },
                 "td": { "class": "p-1" },
                 "th": { "class": "table-secondary p-1" }
                }

    def render_user(self, record):
        user = record.user
        prefix = "" if self.is_collaborator_table else "_"
        hidden = f"""
<input type="hidden" name="{prefix}uservolumebinding_id" value="{record.id}">
        """ if record.id else f"""
<input type="hidden" name="{prefix}user_id" value="{record.user.id}">
        """
        dhidden = "me-2" if self.is_collaborator_table else 'class="me-2 d-none"'
        chk = "checked" if self.is_collaborator_table and record.role == record.RL_ADMIN else ""
        o_adm = "opacity-75" if self.is_collaborator_table and record.role == record.RL_ADMIN else ""
        o_nadm = "" if self.is_collaborator_table and record.role == record.RL_ADMIN else "opacity-75"
        return format_html(f"""
<span id="d-{user.id}" {dhidden}><input id="admin-{user.id}" data-size="small"
  type="checkbox" data-toggle="toggle" name="{prefix}admin_id"
  data-on="<span class='oi oi-lock-unlocked'></span>"
  data-off="<span class='oi oi-lock-locked'></span>"
  data-onstyle="success {o_adm}" data-offstyle="danger {o_nadm}" {chk} value="{user.id}"></span>
{ru(user)}
<input type="hidden" id="search-collaborator-{user.id}" value="{user.username} {user.first_name} {user.last_name} {user.first_name}">
{hidden}
        """)


    def __init__(self, volume, user, collaborator_table):
        collaborators = UserVolumeBinding.objects.filter(volume = volume)
        self.is_collaborator_table = collaborator_table
        if collaborator_table:
            bindings = collaborators.exclude(user = user)
        else:
            profiles = user.profile.everybodyelse.exclude(user__in = [ b.user for b in collaborators ])
            bindings = [ UserVolumeBinding(user = p.user, volume = volume) for p in profiles ]
        self.Meta.attrs["id"] = "collaborators" if collaborator_table else "users"
        super().__init__(bindings)
