"""Role desks and module access. One map for the API, the web app, and the phone app."""

ALL_MODULES = (
    'leads',
    'clients',
    'projects',
    'tasks',
    'followups',
    'team',
    'people',
    'billing',
    'reports',
    'whatsapp',
    'marketing',
    'seo',
    'products',
    'servers',
    'knowledge',
    'settings',
    'office',
    'interns',
)

# Older checkboxes stored these names. Keep them working.
ALIASES = {
    'finance': 'billing',
    'infrastructure': 'servers',
}

ROLE_MODULES = {
    'superadmin': ALL_MODULES,
    'admin': ALL_MODULES,
    'manager': (
        'leads', 'clients', 'projects', 'tasks', 'followups', 'team',
        'people', 'reports', 'whatsapp', 'knowledge', 'office', 'interns',
    ),
    'hr': ('tasks', 'team', 'people', 'knowledge', 'office', 'interns'),
    'finance': ('clients', 'tasks', 'team', 'billing', 'reports', 'knowledge', 'office'),
    'developer': ('projects', 'tasks', 'products', 'whatsapp', 'knowledge', 'team', 'office'),
    'designer': ('projects', 'tasks', 'products', 'whatsapp', 'knowledge', 'team', 'office'),
    'marketer': ('leads', 'tasks', 'followups', 'marketing', 'seo', 'whatsapp', 'knowledge', 'team', 'office'),
    'support': ('clients', 'tasks', 'followups', 'whatsapp', 'knowledge', 'team', 'office'),
    'intern': ('tasks', 'team', 'knowledge', 'office', 'interns'),
}

DESKS = {
    'superadmin': ('Agency desk', 'The whole studio, in one place.'),
    'admin': ('Agency desk', 'The team, the work, and the money.'),
    'manager': ('Studio desk', 'Delivery, the pipeline, and the people on the floor.'),
    'hr': ('People desk', 'Who is in, who is missing, and which leave needs a decision.'),
    'finance': ('Money desk', 'What is collected, what is still owed, and what to chase today.'),
    'developer': ('Build desk', 'Punch in, then finish the tasks that are due today.'),
    'designer': ('Build desk', 'Punch in, then finish the tasks that are due today.'),
    'marketer': ('Growth desk', 'Today’s leads, follow-ups, and campaigns.'),
    'support': ('Care desk', 'Clients who are waiting, and the next follow-up.'),
    'intern': ('Test desk', 'Sign in like staff, test the app, and file what you found.'),
}


def modules_for(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return set()
    role = getattr(user, 'role', None) or 'developer'
    if role in ('superadmin', 'admin'):
        base = set(ALL_MODULES)
    else:
        base = set(ROLE_MODULES.get(role, ROLE_MODULES['developer']))
    extra = getattr(user, 'custom_permissions', None) or []
    if isinstance(extra, str):
        extra = [extra]
    for item in extra:
        key = ALIASES.get(str(item).strip().lower(), str(item).strip().lower())
        if key in ALL_MODULES:
            base.add(key)
    return base


def can(user, module):
    return module in modules_for(user)


def can_manage_people(user):
    return can(user, 'people')


def desk_for(user):
    role = getattr(user, 'role', None) or 'developer'
    name, blurb = DESKS.get(role, DESKS['developer'])
    return {'role': role, 'name': name, 'blurb': blurb}


def module_for_path(path):
    """Return the module a URL belongs to, or None when every signed-in user may call it."""
    if not path.startswith('/api/'):
        return None
    if path.startswith('/api/whatsapp/webhook'):
        return None
    if path.startswith((
        '/api/auth/',
        '/api/notifications/',
        '/api/dashboard/',
        '/api/search/',
        '/api/team/',
    )):
        return None
    if path.startswith('/api/reports/sales'):
        return 'leads'
    if path.startswith('/api/reports/projects'):
        return 'projects'
    prefixes = (
        ('/api/leads/', 'leads'),
        ('/api/clients/', 'clients'),
        ('/api/projects/', 'projects'),
        ('/api/tasks/', 'tasks'),
        ('/api/followups/', 'followups'),
        ('/api/finance/', 'billing'),
        ('/api/marketing/', 'marketing'),
        ('/api/seo/', 'seo'),
        ('/api/products/', 'products'),
        ('/api/servers/', 'servers'),
        ('/api/knowledge/', 'knowledge'),
        ('/api/reports/', 'reports'),
        ('/api/whatsapp/', 'whatsapp'),
        ('/api/office/', 'office'),
        ('/api/interns/', 'interns'),
    )
    for prefix, module in prefixes:
        if path.startswith(prefix):
            return module
    return None
