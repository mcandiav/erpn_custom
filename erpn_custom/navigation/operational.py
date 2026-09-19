"""Operational desk UX for FRAgallardo roles (Spec 011).

Frappe v16 treats Desktop as a first-class screen; default Workspace only
affects login landing (frappe#38691). Module Profile does not hide Desktop
Icons (frappe#41702). This module filters boot desktop_icons for eligible
operational users so /desk is not a module zoo, without touching Admin.
"""

from __future__ import annotations

import frappe

# Role → Workspace name. Extend later for PagosFRA / DespachoFRA / etc.
OPERATIONAL_HOME_BY_ROLE = {
	"ComercialFRA": "ComercialFRA",
}

ADMIN_ROLES = frozenset({"Administrator", "System Manager"})


def get_operational_target_workspace(user: str | None = None) -> str | None:
	user = user or frappe.session.user
	if not user or user in ("Guest", "Administrator"):
		return None

	roles = set(frappe.get_roles(user))
	if roles & ADMIN_ROLES:
		return None

	default_workspace = frappe.db.get_value("User", user, "default_workspace")
	if not default_workspace:
		return None

	for role, workspace in OPERATIONAL_HOME_BY_ROLE.items():
		if role in roles and default_workspace == workspace:
			return workspace
	return None


def is_operational_user(user: str | None = None) -> bool:
	return bool(get_operational_target_workspace(user))


def _icon_matches_workspace(icon: dict, workspace: str) -> bool:
	target = (workspace or "").strip().lower()
	if not target:
		return False
	label = (icon.get("label") or "").strip().lower()
	link_to = (icon.get("link_to") or "").strip().lower()
	return label == target or link_to == target


def apply_operational_desktop(bootinfo) -> None:
	"""Keep only the operational Workspace icon on Desktop for eligible users."""
	workspace = get_operational_target_workspace()
	if not workspace:
		return

	icons = list(bootinfo.get("desktop_icons") or [])
	bootinfo["desktop_icons"] = [icon for icon in icons if _icon_matches_workspace(icon, workspace)]


def extend_bootinfo(bootinfo) -> None:
	apply_operational_desktop(bootinfo)
