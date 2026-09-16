app_name = "erpn_custom"
app_title = "ERPn Custom"
app_publisher = "At-Once-Ai"
app_description = "Customizaciones FRAgallardo para ERPNext, normativa Chile e integraciones."
app_email = "mcchile.cl@gmail.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "erpn_custom",
		"title": "Pagos de Clientes",
		"route": "/desk/pagos-de-clientes",
		"has_permission": "erpn_custom.chile.deposit_mapping.has_vinculador_permission",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erpn_custom/css/erpn_custom.css"
# app_include_js = "/assets/erpn_custom/js/erpn_custom.js"

# include js, css files in header of web template
# web_include_css = "/assets/erpn_custom/css/erpn_custom.css"
# web_include_js = "/assets/erpn_custom/js/erpn_custom.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "erpn_custom/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Bank Statement Import": "public/js/bank_statement_import.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "erpn_custom/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "erpn_custom.utils.jinja_methods",
# 	"filters": "erpn_custom.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "erpn_custom.install.before_install"
# after_install = "erpn_custom.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "erpn_custom.uninstall.before_uninstall"
# after_uninstall = "erpn_custom.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "erpn_custom.utils.before_app_install"
# after_app_install = "erpn_custom.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "erpn_custom.utils.before_app_uninstall"
# after_app_uninstall = "erpn_custom.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "erpn_custom.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpn_custom.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Bank Transaction": {
		"validate": "erpn_custom.chile.ingest.validate_ingest",
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"all": [
		"erpn_custom.chile.deposit_mapping.tick_from_scheduler"
	]
}

# Testing
# -------

# before_tests = "erpn_custom.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
extend_doctype_class = {
	"Bank Statement Import": [
		"erpn_custom.integrations.banco_chile_import.BancoChileStatementImportMixin"
	],
}

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"erpnext.accounts.doctype.bank_statement_import.bank_statement_import.form_start_import": (
		"erpn_custom.integrations.banco_chile_import.form_start_import"
	),
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "erpn_custom.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["erpn_custom.utils.before_request"]
# after_request = ["erpn_custom.utils.after_request"]

# Job Events
# ----------
# before_job = ["erpn_custom.utils.before_job"]
# after_job = ["erpn_custom.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"erpn_custom.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

