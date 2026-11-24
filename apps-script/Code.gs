/**
 * Lead capture for Sourcemap pages.
 * Receives the form on the page, adds a row to the leads sheet in Google Drive,
 * and posts a notice to Slack.
 *
 * Setup: Project Settings, Script Properties, add SLACK_WEBHOOK_URL.
 * Deploy: Deploy, New deployment, Web app, Execute as "Me", Who has access "Anyone".
 */
const SHEET_ID = "1GFmNghw4EGiy_cfhR8UZj78TAG-gFV55K2adp-NM-98";
const LIMITS = { name: 120, email: 160, company: 160, role: 120, rules: 200, message: 2000, check: 300, page: 300, referrer: 300 };

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    // The "website" field is hidden from people. Only automated senders fill it in.
    if (d.website) return reply();
    const lead = {};
    Object.keys(LIMITS).forEach(function (k) {
      const v = Array.isArray(d[k]) ? d[k].join(", ") : String(d[k] || "");
      lead[k] = v.trim().slice(0, LIMITS[k]);
    });
    if (!lead.name || !lead.company || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(lead.email)) return reply();

    const sheet = SpreadsheetApp.openById(SHEET_ID).getSheets()[0];
    sheet.appendRow([new Date(), lead.name, lead.email, lead.company, lead.role, lead.rules,
      lead.message, lead.check, lead.page, lead.referrer].map(safeCell));

    notifySlack(lead);
  } catch (err) {
    console.error(err);
  }
  return reply();
}

// A cell that starts with =, +, - or @ would run as a formula. The apostrophe keeps it as text.
function safeCell(v) {
  return typeof v === "string" && /^[=+\-@]/.test(v) ? "'" + v : v;
}

function notifySlack(lead) {
  const url = PropertiesService.getScriptProperties().getProperty("SLACK_WEBHOOK_URL");
  if (!url) return;
  const lines = [
    "New request from the US supply chain rules page",
    "Name: " + lead.name,
    "Company: " + lead.company + (lead.role ? " (" + lead.role + ")" : ""),
    "Email: " + lead.email,
    lead.rules ? "Rules: " + lead.rules : "",
    lead.check ? "Self-check: " + lead.check : "",
    lead.message ? "Message: " + lead.message : "",
    "Sheet: https://docs.google.com/spreadsheets/d/" + SHEET_ID,
  ].filter(String).map(slackText);
  UrlFetchApp.fetch(url, {
    method: "post", contentType: "application/json", muteHttpExceptions: true,
    payload: JSON.stringify({ text: lines.join("\n") }),
  });
}

// Slack reads <, > and & as markup. Escaping them stops a form entry from tagging a channel.
function slackText(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function reply() {
  return ContentService.createTextOutput(JSON.stringify({ ok: true })).setMimeType(ContentService.MimeType.JSON);
}

// Run this once from the editor to check the sheet and Slack before going live.
function testLead() {
  doPost({ postData: { contents: JSON.stringify({ name: "Test Person", email: "test@example.com",
    company: "Test Company", role: "Tester", rules: ["EO 14411"], message: "Test entry. Delete this row.",
    check: "import: yes", page: "test", referrer: "" }) } });
}
