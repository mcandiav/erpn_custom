frappe.pages["pagos-huerfanos"].on_page_load = function () {
	frappe.set_route("List", "Bank Transaction", {
		party: ["is", "not set"],
		deposit: [">", 0],
		docstatus: ["<", 2],
	});
};
