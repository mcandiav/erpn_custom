/**
 * Operational navigation guard for FRAgallardo Desk UX (Spec 011).
 *
 * Server-side extend_bootinfo filters Desktop Icons for operational users.
 * This client guard only redirects exact Desk root (/desk) to the user's
 * default operational Workspace. Administrator / System Manager are excluded.
 *
 * Upstream context:
 * - https://github.com/frappe/frappe/issues/41702
 * - https://github.com/frappe/frappe/issues/38691
 * - https://github.com/frappe/frappe/issues/24249
 * - https://github.com/frappe/frappe/pull/39927
 */
frappe.provide("erpn_custom.operational_navigation");

(function () {
	"use strict";

	const OPERATIONAL_HOME_BY_ROLE = {
		ComercialFRA: "ComercialFRA",
	};
	const ADMIN_ROLES = ["Administrator", "System Manager"];
	const RETRY_MS = [0, 100, 400];

	let redirecting = false;
	let initialized = false;

	function get_default_workspace_name() {
		const dw = frappe.boot && frappe.boot.user && frappe.boot.user.default_workspace;
		if (!dw) {
			return null;
		}
		if (typeof dw === "string") {
			return dw;
		}
		return dw.name || null;
	}

	function get_operational_target_workspace() {
		const default_workspace = get_default_workspace_name();
		if (!default_workspace) {
			return null;
		}
		for (const [role, workspace] of Object.entries(OPERATIONAL_HOME_BY_ROLE)) {
			if (frappe.user.has_role(role) && default_workspace === workspace) {
				return workspace;
			}
		}
		return null;
	}

	function is_admin_user() {
		if (frappe.session.user === "Administrator") {
			return true;
		}
		return ADMIN_ROLES.some((role) => frappe.user.has_role(role));
	}

	function is_operational_user() {
		if (!frappe.boot || !frappe.boot.user || is_admin_user()) {
			return false;
		}
		return Boolean(get_operational_target_workspace());
	}

	function is_desk_root_route() {
		const path = (window.location.pathname || "").replace(/\/+$/, "") || "/desk";
		if (path === "/desk") {
			return true;
		}
		const route = (frappe.get_route && frappe.get_route()) || [];
		return !route.length || !route[0];
	}

	function workspace_slug(workspace_name) {
		if (frappe.router && typeof frappe.router.slug === "function") {
			return frappe.router.slug(workspace_name);
		}
		return String(workspace_name || "")
			.toLowerCase()
			.replace(/ /g, "-");
	}

	function redirect_operational_home_if_needed() {
		if (redirecting || !is_operational_user() || !is_desk_root_route()) {
			return false;
		}
		const target = get_operational_target_workspace();
		if (!target || !frappe.workspaces || !frappe.workspaces[workspace_slug(target)]) {
			return false;
		}

		redirecting = true;
		frappe.route_flags = frappe.route_flags || {};
		frappe.route_flags.replace_route = true;
		setTimeout(() => {
			try {
				frappe.set_route(workspace_slug(target));
			} finally {
				redirecting = false;
			}
		}, 0);
		return true;
	}

	function init() {
		if (initialized) {
			return;
		}
		initialized = true;
		redirect_operational_home_if_needed();
		RETRY_MS.forEach((delay) => {
			setTimeout(redirect_operational_home_if_needed, delay);
		});
		if (frappe.router && typeof frappe.router.on === "function") {
			frappe.router.on("change", redirect_operational_home_if_needed);
		}
	}

	erpn_custom.operational_navigation = {
		OPERATIONAL_HOME_BY_ROLE,
		is_operational_user,
		is_desk_root_route,
		get_operational_target_workspace,
		redirect_operational_home_if_needed,
		init,
	};

	if (frappe.boot) {
		init();
	}
	frappe.ready(init);
})();
