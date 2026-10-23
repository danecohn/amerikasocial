/* AltStack Box: the "amerika" colour theme for BeepBox (neon on dark chrome). Derived from BeepBox's own "dark classic"
 * variables at start-up, so upstream themes stay untouched and new upstream variables are inherited. */
(function (root) {
	"use strict";
	const NS = (root.Amerika = root.Amerika || {});
	const OVERRIDES = {
		"--page-margin": "#e7edf3", "--editor-background": "#f8fafc", "--hover-preview": "#ffffff", "--playhead": "#ffb02e",
		"--primary-text": "#233649", "--secondary-text": "#51677c", "--inverted-text": "#f8fafc", "--text-selection": "rgba(255,61,240,0.55)",
		"--box-selection-fill": "rgba(25,227,255,0.18)", "--loop-accent": "#1764bd", "--link-accent": "#237dcc",
		"--ui-widget-background": "#dbe5ee", "--ui-widget-focus": "#bfd8ed", "--pitch-background": "#e7edf3", "--tonic": "#5a3a2a", "--fifth-note": "#1d4560",
		"--white-piano-key": "#d9d9ee", "--black-piano-key": "#2a2750",
	};
	function css() {
		let base = root.beepbox.ColorConfig.themes["light classic"];
		Object.keys(OVERRIDES).forEach(function (k) {
			const re = new RegExp("(" + k.replace(/[-]/g, "\\-") + "\\s*:)[^;]+;");
			base = re.test(base) ? base.replace(re, "$1 " + OVERRIDES[k] + ";") : base.replace(":root {", ":root {\n\t\t\t\t" + k + ": " + OVERRIDES[k] + ";");
		});
		return base;
	}
	NS.theme = {
		name: "amerika",
		install: function () { root.beepbox.ColorConfig.themes["amerika"] = css(); },
		names: ["amerika", "dark classic", "light classic"],
	};
})(typeof window !== "undefined" ? window : globalThis);
