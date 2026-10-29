#!/usr/bin/env node
// =============================================================================
// Generate a dashboard key and its one-tap unlock link.
//
//   node tools/new-dashboard-key.mjs [site-url]
//
// Run it in your own terminal, not inside an agent session, so the key never
// lands in a transcript. Put the first line in the cloud environment's
// variables. Save the link as a bookmark or in your password manager: opening
// it once per device unlocks the dashboard there for good. A new key replaces
// the old one on the next daily run, and old links then stop working.
// =============================================================================
import { generateKeyText } from "../site/js/crypto.js";

const site = (process.argv[2] || "https://skathio.github.io/stonks/").replace(/#.*$/, "");
const key = generateKeyText();
console.log(`STONKS_DASHBOARD_KEY=${key}`);
console.log(`Unlock link: ${site}#k=${key}`);
