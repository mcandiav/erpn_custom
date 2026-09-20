/**
 * Operational navigation guard for FRAgallardo Desk UX (Spec 011).
 *
 * Applies ONLY when:
 * - user has a mapped operational role (e.g. ComercialFRA), and
 * - User.default_workspace matches that role's workspace, and
 * - user is NOT Administrator / System Manager.
 *
 * Other profiles keep stock Frappe Home/Desktop behavior.
 *
 * Strategy: hard-redirect Home/Desktop/`/desk` to the operational Workspace
 * via location.replace (reliable on Frappe v16). No synthetic Desktop Icons.
 */
frappe.provide("erpn_custom.operational_navigation");

(function () {
	"use strict";

	const OPERATIONAL_HOME_BY_ROLE = {
		ComercialFRA: "ComercialFRA",
	};
	const ADMIN_ROLES = ["Administrator", "System Manager"];
	const RETRY_MS = [0, 100, 300, 800];

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

	function workspace_slug(workspace_name) {
		if (frappe.router && typeof frappe.router.slug === "function") {
			return frappe.router.slug(workspace_name);
		}
		return String(workspace_name || "")
			.toLowerCase()
			.replace(/ /g, "-");
	}

	function is_already_on_operational_home(target) {
		if (!target) {
			return false;
		}
		const slug = workspace_slug(target);
		const path = (window.location.pathname || "").replace(/\/+$/, "") || "/desk";
		if (path === `/desk/${slug}`) {
			return true;
		}
		const route = (frappe.get_route && frappe.get_route()) || [];
		const first = route[0] || "";
		const second = route[1] || "";
		if (first === "Workspaces" && second === target) {
			return true;
		}
		if (String(first).toLowerCase() === slug) {
			return true;
		}
		return false;
	}

	function is_desk_root_route() {
		const target = get_operational_target_workspace();
		if (is_already_on_operational_home(target)) {
			return false;
		}

		const path = (window.location.pathname || "").replace(/\/+$/, "") || "/desk";
		if (path === "/desk" || path === "/desk/home") {
			return true;
		}

		const route = (frappe.get_route && frappe.get_route()) || [];
		const first = route[0] || "";
		const second = route[1] || "";

		if (!first) {
			return true;
		}
		if (first === "Workspaces" && !second) {
			return true;
		}
		if (first === "Workspaces" && (second === "home" || second === "Home")) {
			return true;
		}
		if (first === "desktop" || first === "Desktop") {
			return true;
		}
		return false;
	}

	function redirect_operational_home_if_needed() {
		if (redirecting || !is_operational_user()) {
			return false;
		}
		if (!is_desk_root_route()) {
			return false;
		}
		const target = get_operational_target_workspace();
		if (!target) {
			return false;
		}
		const slug = workspace_slug(target);
		// Prefer hard navigation: frappe.set_route is unreliable while Desktop mounts.
		redirecting = true;
		window.location.replace(`/desk/${slug}`);
		return true;
	}

	function init() {
		redirect_operational_home_if_needed();
		if (initialized) {
			return;
		}
		initialized = true;
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
