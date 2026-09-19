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
 * Administrator / System Manager are never redirected.
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
	let original_router_set_route = null;

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
		const path = (window.location.pathname || "").replace(/\/+$/, "") || "/desk";
		if (path === "/desk" || path === "/desk/home") {
			return true;
		}

		const route = (frappe.get_route && frappe.get_route()) || [];
		if (!route.length || !route[0]) {
			return true;
		}
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
		return Boolean(frappe.workspaces[workspace_slug(workspace_name)]);
	}

	function args_mean_desk_root(args) {
		if (!args || !args.length) {
			return true;
		}
		if (args.length === 1) {
			const a = args[0];
			if (Array.isArray(a)) {
				return (
					!a.length ||
					!a[0] ||
					(a[0] === "Workspaces" && String(a[1] || "").toLowerCase() === "home")
				);
			}
			if (typeof a === "string") {
				const s = a.replace(/\/+$/, "");
				return (
					s === "" ||
					s === "/desk" ||
					s === "desk" ||
					s === "/desk/home" ||
					s === "home"
				);
			}
		}
		return false;
	}

	function call_router_set_route() {
		const fn = original_router_set_route || frappe.router.set_route;
		return fn.apply(frappe.router, arguments);
	}

	function go_operational_home() {
		const target = get_operational_target_workspace();
		if (!target || !workspace_route_available(target)) {
			return false;
		}
		const slug = workspace_slug(target);
		frappe.route_flags = frappe.route_flags || {};
		frappe.route_flags.replace_route = true;
		call_router_set_route(slug);
		return true;
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
		if (!workspace_route_available(get_operational_target_workspace())) {
			return false;
		}

		redirecting = true;
		// Defer so we do not fight an in-flight route() to /desk (Desktop menu / breadcrumb).
		setTimeout(() => {
			try {
				go_operational_home();
			} finally {
				redirecting = false;
			}
		}, 0);
		return true;
	}

	function intercept_desk_home_clicks() {
		// Breadcrumb home icon uses href="/desk" (breadcrumbs.js clear()).
		$(document).on("click", 'a[href="/desk"], a[href="/desk/"]', function (e) {
			if (!is_operational_user()) {
				return;
			}
			e.preventDefault();
			e.stopPropagation();
			go_operational_home();
			return false;
		});

		// Sidebar header menu item "Desktop" (sidebar_header.js).
		$(document).on("click", '.dropdown-menu-item[data-name="desktop"]', function (e) {
			if (!is_operational_user()) {
				return;
			}
			e.preventDefault();
			e.stopPropagation();
			go_operational_home();
			return false;
		});
	}

	function wrap_router_set_route() {
		if (original_router_set_route || !frappe.router || !frappe.router.set_route) {
			return;
		}
		original_router_set_route = frappe.router.set_route.bind(frappe.router);
		frappe.router.set_route = function () {
			const args = Array.from(arguments);
			if (is_operational_user() && args_mean_desk_root(args)) {
				const target = get_operational_target_workspace();
				if (target && workspace_route_available(target)) {
					frappe.route_flags = frappe.route_flags || {};
					frappe.route_flags.replace_route = true;
					return original_router_set_route(workspace_slug(target));
				}
			}
			return original_router_set_route.apply(frappe.router, args);
		};
	}

	function schedule_retries() {
		RETRY_MS.forEach((delay) => {
			setTimeout(() => {
				if (is_desk_root_route()) {
					redirect_operational_home_if_needed();
				}
			}, delay);
		});
	}

	function init() {
		if (initialized) {
			return;
		}
		initialized = true;

		wrap_router_set_route();
		intercept_desk_home_clicks();
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
