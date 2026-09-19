/**
 * Operational navigation guard for FRAgallardo Desk UX.
 *
 * Workaround for Frappe v16 Desktop / default-workspace routing gaps:
 * - https://github.com/frappe/frappe/issues/41702
 * - https://github.com/frappe/frappe/issues/40517
 * - https://github.com/frappe/frappe/issues/24249
 * - https://github.com/frappe/frappe/pull/39927
 *
 * Security stays in Role Permissions. This file only redirects Desk root
 * (/desk) to the configured operational Workspace for eligible users.
 */
frappe.provide("erpn_custom.operational_navigation");

(function () {
	"use strict";

	// Role → Workspace name. Extend later for PagosFRA / DespachoFRA / etc.
	const OPERATIONAL_HOME_BY_ROLE = {
		ComercialFRA: "ComercialFRA",
	};

	const ADMIN_ROLES = ["Administrator", "System Manager"];
	const RETRY_MS = [0, 50, 150, 400, 1000];

	let redirecting = false;
	let initialized = false;
	let attempts = 0;

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
		if (!frappe.boot || !frappe.boot.user) {
			return false;
		}
		if (is_admin_user()) {
			return false;
		}
		return Boolean(get_operational_target_workspace());
	}

	function is_desk_root_route() {
		// Exact Desktop Icons home (/desk) and Frappe v16 logo/Home target (/desk/home).
		const path = (window.location.pathname || "").replace(/\/+$/, "") || "/desk";
		if (path === "/desk" || path === "/desk/home") {
			return true;
		}

		const route = (frappe.get_route && frappe.get_route()) || [];
		if (!route.length || !route[0]) {
			return true;
		}
		// Standard route form for public Home workspace.
		if (
			route[0] === "Workspaces" &&
			route.length === 2 &&
			String(route[1] || "").toLowerCase() === "home"
		) {
			return true;
		}
		return false;
	}

	function workspace_slug(workspace_name) {
		if (frappe.router && typeof frappe.router.slug === "function") {
			return frappe.router.slug(workspace_name);
		}
		return String(workspace_name || "")
			.toLowerCase()
			.replace(/ /g, "-");
	}

	function workspace_route_available(workspace_name) {
		if (!frappe.workspaces) {
			return false;
		}
		const slug = workspace_slug(workspace_name);
		return Boolean(frappe.workspaces[slug]);
	}

	function redirect_operational_home_if_needed() {
		if (redirecting) {
			return false;
		}
		if (!is_operational_user()) {
			return false;
		}
		if (!is_desk_root_route()) {
			return false;
		}

		const target = get_operational_target_workspace();
		if (!target) {
			return false;
		}
		// Boot may populate workspaces slightly after ready; retry instead of giving up.
		if (!workspace_route_available(target)) {
			return false;
		}

		redirecting = true;
		const slug = workspace_slug(target);
		frappe.route_flags = frappe.route_flags || {};
		frappe.route_flags.replace_route = true;

		Promise.resolve(frappe.set_route(slug))
			.catch(() => {
				// Last-resort navigation if router rejects the transition.
				if (is_desk_root_route()) {
					window.location.replace("/desk/" + encodeURIComponent(slug));
				}
			})
			.finally(() => {
				redirecting = false;
			});

		return true;
	}

	function schedule_retries() {
		RETRY_MS.forEach((delay) => {
			setTimeout(() => {
				if (!is_desk_root_route()) {
					return;
				}
				attempts += 1;
				redirect_operational_home_if_needed();
			}, delay);
		});
	}

	function init() {
		if (initialized) {
			return;
		}
		initialized = true;

		redirect_operational_home_if_needed();
		schedule_retries();

		if (frappe.router && typeof frappe.router.on === "function") {
			frappe.router.on("change", () => {
				redirect_operational_home_if_needed();
			});
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
	frappe.ready(() => {
		init();
	});
})();
