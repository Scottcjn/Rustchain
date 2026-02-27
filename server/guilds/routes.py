"""Route stubs for RIP-201 guild APIs."""

def create_guild(request):
    return {"ok": False, "error": "not_implemented", "route": "create_guild"}, 501

def get_guild(request, guild_id):
    return {"ok": False, "error": "not_implemented", "route": "get_guild", "guild_id": guild_id}, 501

def add_member(request, guild_id):
    return {"ok": False, "error": "not_implemented", "route": "add_member", "guild_id": guild_id}, 501
