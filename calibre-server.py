#!/usr/bin/env python3
"""Calibre Library Web Server – multi‑select filters, series, dynamic formats, theming."""

import argparse, base64, io, logging, re, shutil, sqlite3, tempfile, zipfile
from pathlib import Path
from flask import Flask, abort, render_template_string, request, send_file, send_from_directory, jsonify

logging.getLogger('waitress.queue').setLevel(logging.ERROR)

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📚 Calibre Library</title>
<style>
	/* ── CSS variables (default dark) ── */
	:root {
		--bg: #0f1117;
		--surface: #1a1d27;
		--card: #22253a;
		--accent: #7c6aff;
		--accent2: #a78bfa;
		--text: #e2e8f0;
		--muted: #8892a4;
		--border: #2e3350;
		--green: #4ade80;
	}
	body.no-scroll { overflow: hidden; }
	* { box-sizing: border-box; margin: 0; padding: 0; }
	body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; transition: background 0.2s, color 0.2s; }

	/* ── Header ── */
	header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 0.8rem 2rem; display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
	header h1 { font-size: 1.4rem; font-weight: 700; color: var(--accent2); }
	#search-box { flex: 1; min-width: 200px; background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.95rem; outline: none; }
	#search-box:focus { border-color: var(--accent); }
	.btn { cursor: pointer; border: none; border-radius: 7px; padding: 0.4rem 1rem; font-size: 0.85rem; font-weight: 600; transition: opacity 0.15s; background: var(--card); color: var(--text); border: 1px solid var(--border); }
	.btn:hover { opacity: 0.85; background: var(--accent); color: white; border-color: var(--accent); }
	.btn-outline { background: transparent; color: var(--accent2); border: 1px solid var(--accent); }
	.btn-sm { padding: 0.2rem 0.7rem; font-size: 0.78rem; }
	.btn-dl { background: #2d4a22; color: var(--green); border-color: #3d6b2e; }

	/* ── Filters bar ── */
	#filters { position: relative; background: var(--surface); border-bottom: 1px solid var(--border); padding: 0.6rem 2rem; display: flex; gap: 0.8rem; flex-wrap: wrap; align-items: flex-start; }
	#resize-handle { position: absolute; bottom: 0; left: 0; right: 0; height: 10px; background: var(--border); text-align: center; line-height: 8px; font-size: 12px; letter-spacing: 2px; color: var(--muted); cursor: ns-resize; user-select: none; border-radius: 0 0 6px 6px; }
	#resize-handle:hover { background: var(--accent); color: white; }
	#filters label { color: var(--muted); font-size: 0.8rem; margin-top: 0.2rem; }
	#filters select { background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 0.3rem; border-radius: 6px; font-size: 0.8rem; min-width: 120px; }
	select[multiple] { overflow: auto; min-height: 70px; }

	/* ── Tags pills ── */
	.tag-pill { background: var(--card); border: 1px solid var(--border); color: var(--accent2); padding: 0.2rem 0.65rem; border-radius: 99px; font-size: 0.76rem; cursor: pointer; display: inline-block; margin: 0.1rem; }
	.tag-pill:hover { background: var(--accent); color: #fff; border-color: var(--accent); }
	#result-count { margin-left: auto; color: var(--muted); font-size: 0.82rem; white-space: nowrap; }

	/* ── Book grid ── */
	#grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 1.2rem; padding: 1.5rem 2rem; }
	.book-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; cursor: pointer; transition: transform 0.15s, border-color 0.15s; }
	.book-card:hover { transform: translateY(-3px); border-color: var(--accent); }
	.book-card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; background: var(--surface); }
	.book-card .no-cover { width: 100%; aspect-ratio: 2/3; display: flex; align-items: center; justify-content: center; font-size: 2.5rem; background: var(--surface); }
	.book-info { padding: 0.6rem; flex: 1; display: flex; flex-direction: column; gap: 0.2rem; }
	.book-title { font-size: 0.82rem; font-weight: 600; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
	.book-author { font-size: 0.74rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.book-series { font-size: 0.72rem; color: var(--accent2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-style: italic; }
	.book-formats { display: flex; gap: 0.25rem; flex-wrap: wrap; margin-top: 0.3rem; }
	.fmt-badge { background: #1e2640; color: var(--accent2); border: 1px solid var(--border); padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.68rem; font-weight: 700; }
	.book-progress-wrap { height: 3px; background: var(--border); margin-top: auto; }
	.book-progress-bar { height: 3px; background: var(--accent); border-radius: 0 2px 2px 0; transition: width 0.3s; }

	/* ── Modal ── */
	#modal-bg { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 100; align-items: center; justify-content: center; }
	#modal-bg.open { display: flex; }
	#modal { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; width: min(680px, 95vw); max-height: 88vh; overflow-y: auto; padding: 1.5rem; position: relative; }
	#modal-close { position: absolute; top: 1rem; right: 1rem; background: none; border: none; color: var(--muted); font-size: 1.4rem; cursor: pointer; }
	#modal-close:hover { color: var(--text); }
	#modal-inner { display: flex; gap: 1.2rem; }
	#modal-cover img, #modal-cover .no-cover-lg { width: 130px; border-radius: 8px; }
	#modal-cover .no-cover-lg { height: 195px; background: var(--card); display: flex; align-items: center; justify-content: center; font-size: 3rem; border-radius: 8px; }
	#modal-meta { flex: 1; display: flex; flex-direction: column; gap: 0.5rem; }
	#modal-title { font-size: 1.1rem; font-weight: 700; }
	#modal-author { color: var(--accent2); font-size: 0.9rem; }
	#modal-series { font-size: 0.84rem; color: var(--muted); font-style: italic; }
	#modal-series span { color: var(--accent2); cursor: pointer; text-decoration: underline dotted; }
	#modal-tags { display: flex; gap: 0.3rem; flex-wrap: wrap; margin-top: 0.2rem; }
	#modal-desc { font-size: 0.83rem; color: var(--muted); line-height: 1.5; margin-top: 0.3rem; max-height: 120px; overflow-y: auto; }
	#modal-dl { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.5rem; }
	.btn-continue { background: #2a1f50; color: var(--accent2); border-color: var(--accent); }
	.btn-continue:hover { background: var(--accent); color: #fff; }

	/* ── Bottom bar and spinner ── */
	#dl-bar { position: fixed; bottom: 0; left: 0; right: 0; background: var(--surface); border-top: 1px solid var(--border); padding: 0.6rem 2rem; display: none; align-items: center; gap: 1rem; z-index: 50; flex-wrap: wrap; }
	#dl-bar.visible { display: flex; }
	#spinner { display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%); z-index: 200; }
	.spin { width: 40px; height: 40px; border: 4px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
	@keyframes spin { to { transform: rotate(360deg); } }
	#empty { text-align: center; padding: 4rem; color: var(--muted); }

	/* ── Settings panel ── */
	#settings-panel { position: fixed; top: 20%; right: 20px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1rem; width: 280px; z-index: 150; box-shadow: 0 4px 12px rgba(0,0,0,0.3); display: none; flex-direction: column; gap: 0.8rem; }
	#settings-panel.open { display: flex; }
	.settings-row { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
	.settings-row label { font-size: 0.8rem; }
	input, select { background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 0.3rem; border-radius: 5px; }
	.color-preview { width: 24px; height: 24px; border-radius: 4px; border: 1px solid var(--border); }
	#gear-icon { cursor: pointer; font-size: 1.4rem; margin-left: 0.5rem; color: var(--accent2); }
	@media (max-width: 700px) { select[multiple] { min-width: 100px; } #settings-panel { width: 260px; right: 10px; top: 10%; } }

	/* ── Reader overlay ── */
	#reader-overlay { display: none; position: fixed; inset: 0; background: var(--bg); z-index: 300; flex-direction: column; }
	#reader-overlay.open { display: flex; }
	#reader-toolbar { background: var(--surface); border-bottom: 1px solid var(--border); padding: 0.5rem 1.2rem; display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap; flex-shrink: 0; }
	#reader-toolbar .reader-title { flex: 1; font-weight: 600; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--accent2); }
	#reader-body { flex: 1; overflow: hidden; position: relative; }
	#epub-viewer { width: 100%; height: 100%; overflow-y: auto; }
	#epub-area { width: 100%; min-height: 100%; }
	#pdf-viewer { width: 100%; height: 100%; border: none; }
	#txt-viewer { width: 100%; height: 100%; overflow-y: auto; padding: 2rem max(2rem, calc(50% - 380px)); line-height: 1.8; font-size: var(--reader-font-size, 1rem); color: var(--text); white-space: pre-wrap; word-break: break-word; }
	#cbz-viewer { width: 100%; height: 100%; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; align-items: center; gap: 1rem; }
	#cbz-viewer img { max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
	.btn-read { background: #1a2e40; color: #60c0f0; border-color: #2a4a60; }
	.btn-read:hover { background: #2a4a60; border-color: #60c0f0; }
	#toc-panel { position: absolute; top: 0; left: 0; bottom: 0; width: 280px; background: var(--surface); border-right: 1px solid var(--border); z-index: 20; overflow-y: auto; transform: translateX(-100%); transition: transform 0.2s; display: flex; flex-direction: column; }
	#toc-panel.open { transform: translateX(0); }
	#toc-panel h3 { padding: 0.8rem 1rem; font-size: 0.85rem; color: var(--accent2); border-bottom: 1px solid var(--border); flex-shrink: 0; }
	.toc-item { padding: 0.5rem 1rem; font-size: 0.82rem; cursor: pointer; border-bottom: 1px solid var(--border); color: var(--text); }
	.toc-item:hover { background: var(--card); color: var(--accent2); }
	.toc-item.sub { padding-left: 1.8rem; font-size: 0.78rem; color: var(--muted); }
</style>
</head>
<body>
<header>
	<h1>📚 Calibre Library</h1>
	<input id="search-box" type="search" placeholder="Search..." autocomplete="off">
	<button class="btn btn-outline btn-sm" onclick="clearFilters()">Clear all</button>
	<span id="gear-icon" onclick="toggleSettings()">⚙️</span>
</header>

<div id="filters">
	<label>Author</label><select id="f-author" multiple size="2" onchange="applyFilters()"></select>
	<label>Series</label><select id="f-series" multiple size="2" onchange="applyFilters()"></select>
	<label>Tag</label><select id="f-tag" multiple size="2" onchange="applyFilters()"></select>
	<label>Format</label><select id="f-format" multiple size="2" onchange="applyFilters()"></select>
	<label>Sort by</label><select id="f-sort" onchange="applyFilters()">
		<option value="title">Title</option><option value="author">Author</option>
		<option value="series">Series</option><option value="date">Date added</option>
	</select>
	<span id="result-count"></span>
	<button id="dl-collection-btn" class="btn btn-dl btn-sm" style="display:none" onclick="downloadCollection()">⬇ Download filtered</button>
	<div id="resize-handle" title="Drag to resize filter panel">⋮⋮⋮</div>
</div>

<div id="grid"><div id="empty">No books match your search.</div></div>

<!-- Settings panel -->
<div id="settings-panel">
	<div class="settings-row"><strong>⚙️ Settings</strong><button class="btn btn-sm" onclick="toggleSettings()">✕</button></div>
	<div class="settings-row"><label>Theme preset:</label><select id="theme-preset" onchange="applyThemePreset()">
		<option value="dark">Dark</option><option value="light">Light</option>
		<option value="sepia">Sepia</option><option value="nord">Nord</option>
		<option value="solarized">Solarized</option>
		<option value="cyberpunk">Cyberpunk</option>
		<option value="xterm">Xterm</option><option value="rainbow">Rainbow</option>
	</select></div>
	<div class="settings-row"><label>Background</label><input type="color" id="color-bg" oninput="updateBackground(this.value)"><span class="color-preview" id="preview-bg"></span></div>
	<div class="settings-row"><label>Card</label><input type="color" id="color-card" oninput="updateColor('--card', this.value)"><span class="color-preview" id="preview-card"></span></div>
	<div class="settings-row"><label>Accent</label><input type="color" id="color-accent" oninput="updateAccent(this.value)"><span class="color-preview" id="preview-accent"></span></div>
	<div class="settings-row"><label>Text</label><input type="color" id="color-text" oninput="updateColor('--text', this.value)"><span class="color-preview" id="preview-text"></span></div>
	<div class="settings-row"><label>Filter panel height (px)</label><input type="number" id="panel-height" step="10" min="120" max="600" onchange="setPanelHeightFromInput(this.value)"></div>
	<div class="settings-row"><label><input type="checkbox" id="auto-save" checked> Auto-save settings</label></div>
	<div class="settings-row"><button class="btn btn-sm" onclick="saveSettings()">Save Now</button><button class="btn btn-sm" onclick="resetSettings()">Reset</button></div>
</div>

<div id="modal-bg" onclick="closeModal(event)"><div id="modal"><button id="modal-close" onclick="closeModal()">✕</button>
<div id="modal-inner"><div id="modal-cover"></div><div id="modal-meta"><div id="modal-title"></div><div id="modal-author"></div>
<div id="modal-series"></div><div id="modal-tags"></div><div id="modal-desc"></div><div id="modal-dl"></div></div></div></div></div>

<div id="dl-bar"><span id="dl-bar-label"></span><button class="btn btn-dl" onclick="downloadCollection()">⬇ Download ZIP</button>
<button class="btn btn-outline btn-sm" onclick="clearFilters()">Clear</button></div>
<div id="spinner"><div class="spin"></div></div>

<!-- Reader overlay -->
<div id="reader-overlay">
	<div id="reader-toolbar">
		<button class="btn btn-sm" onclick="closeReader()">✕ Close</button>
		<button class="btn btn-sm" id="toc-btn" onclick="toggleToc()" style="display:none">📑 TOC</button>
		<span class="reader-title" id="reader-book-title"></span>
		<span style="color:var(--muted);font-size:0.78rem;padding:0.1rem 0.5rem;border:1px solid var(--border);border-radius:4px" id="reader-fmt-badge"></span>
		<button class="btn btn-sm" onclick="readerFontSize(-1)" title="Decrease font size">A−</button>
		<button class="btn btn-sm" onclick="readerFontSize(+1)" title="Increase font size">A+</button>
		<span id="reader-loc" style="color:var(--muted);font-size:0.78rem;margin-left:auto"></span>
	</div>
	<div id="reader-body">
		<div id="toc-panel"><h3>📑 Contents</h3><div id="toc-list"></div></div>
		<iframe id="pdf-viewer" style="display:none"></iframe>
		<div id="txt-viewer" style="display:none"></div>
		<div id="cbz-viewer" style="display:none"></div>
		<div id="epub-viewer" style="display:none; overflow-y:auto;">
			<div id="epub-area" style="width:100%; min-height:100%;"></div>
		</div>
	</div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/epubjs@0.3.93/dist/epub.min.js"></script>
<script>

// ========== GLOBALS ==========
let allBooks = [], filtered = [];
let currentModalBook = null;
const filterPanel = document.getElementById('filters');
const resizeHandle = document.getElementById('resize-handle');
const multiSelects = document.querySelectorAll('select[multiple]');
let startY, startHeight;

// ========== COLOR & SETTINGS MANAGEMENT ==========
function updateBackground(hex) {
	document.documentElement.style.setProperty('--bg', hex);
	document.documentElement.style.setProperty('--surface', hex);
	updateColorPreviews();
	if (document.getElementById('auto-save').checked) saveSettings();
}
function updateAccent(hex) {
	document.documentElement.style.setProperty('--accent', hex);
	document.documentElement.style.setProperty('--accent2', hex);
	updateColorPreviews();
	if (document.getElementById('auto-save').checked) saveSettings();
}
function updateColor(varName, hex) {
	document.documentElement.style.setProperty(varName, hex);
	updateColorPreviews();
	if (document.getElementById('auto-save').checked) saveSettings();
}
function updateColorPreviews() {
	document.getElementById('preview-bg').style.backgroundColor = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
	document.getElementById('preview-card').style.backgroundColor = getComputedStyle(document.documentElement).getPropertyValue('--card').trim();
	document.getElementById('preview-accent').style.backgroundColor = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
	document.getElementById('preview-text').style.backgroundColor = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
}
function setPanelHeightFromInput(h) {
	let val = parseInt(h);
	if (isNaN(val)) return;
	setPanelHeight(val);
	if (document.getElementById('auto-save').checked) saveSettings();
}
function setPanelHeight(h) {
	let newHeight = Math.min(Math.max(h, 120), window.innerHeight * 0.6);
	filterPanel.style.height = newHeight + 'px';
	let selectHeight = newHeight - 20;
	if (selectHeight < 70) selectHeight = 70;
	multiSelects.forEach(sel => sel.style.height = selectHeight + 'px');
	document.getElementById('panel-height').value = newHeight;
}
function applyThemePreset(theme) {
	let preset = theme || document.getElementById('theme-preset').value;
	switch(preset) {
		case 'dark': updateBackground('#0f1117'); updateColor('--card', '#22253a'); updateAccent('#7c6aff'); updateColor('--text', '#e2e8f0'); updateColor('--muted', '#8892a4'); updateColor('--border', '#2e3350'); updateColor('--green', '#4ade80'); break;
		case 'light': updateBackground('#f5f7fa'); updateColor('--card', '#eef2f6'); updateAccent('#3b82f6'); updateColor('--text', '#1e293b'); updateColor('--muted', '#64748b'); updateColor('--border', '#cbd5e1'); updateColor('--green', '#10b981'); break;
		case 'sepia': updateBackground('#fbf7e9'); updateColor('--card', '#f5ecd9'); updateAccent('#b85c1a'); updateColor('--text', '#4a3b2c'); updateColor('--muted', '#7a6a5a'); updateColor('--border', '#d4c5a9'); updateColor('--green', '#6b8e23'); break;
		case 'nord': updateBackground('#2e3440'); updateColor('--card', '#3b4252'); updateAccent('#88c0d0'); updateColor('--text', '#e5e9f0'); updateColor('--muted', '#81a1c1'); updateColor('--border', '#434c5e'); updateColor('--green', '#a3be8c'); break;
		case 'solarized': updateBackground('#002b36'); updateColor('--card', '#073642'); updateAccent('#268bd2'); updateColor('--text', '#839496'); updateColor('--muted', '#586e75'); updateColor('--border', '#0a4b5e'); updateColor('--green', '#859900'); break;
		case 'cyberpunk': updateBackground('#0a0a1a'); updateColor('--card', '#1a1a3a'); updateAccent('#ff00ff'); updateColor('--text', '#00ffff'); updateColor('--muted', '#ff00cc'); updateColor('--border', '#ff00ff'); updateColor('--green', '#00ff9d'); break;
		case 'xterm': updateBackground('#0c0c0c'); updateColor('--card', '#1a1a1a'); updateAccent('#00ff00'); updateColor('--text', '#00ff00'); updateColor('--muted', '#32cd32'); updateColor('--border', '#008000'); updateColor('--green', '#7cfc00'); break;
		case 'rainbow': updateBackground('#1a0a2e'); updateColor('--card', '#2e1a4a'); updateAccent('#ff6b6b'); updateColor('--text', '#ffd93d'); updateColor('--muted', '#6c5ce7'); updateColor('--border', '#ff9f4a'); updateColor('--green', '#4ecdc4'); break;
		default: break;
	}
	document.getElementById('color-bg').value = rgbToHex(getComputedStyle(document.documentElement).getPropertyValue('--bg').trim());
	document.getElementById('color-card').value = rgbToHex(getComputedStyle(document.documentElement).getPropertyValue('--card').trim());
	document.getElementById('color-accent').value = rgbToHex(getComputedStyle(document.documentElement).getPropertyValue('--accent').trim());
	document.getElementById('color-text').value = rgbToHex(getComputedStyle(document.documentElement).getPropertyValue('--text').trim());
	updateColorPreviews();
	if (document.getElementById('auto-save').checked) saveSettings();
}
function rgbToHex(rgb) {
	let match = rgb.match(/^#?([0-9a-f]{6})$/i);
	if (match) return '#' + match[1];
	let res = rgb.match(/\d+/g);
	if (!res) return '#0f1117';
	return '#' + ((1 << 24) + (parseInt(res[0]) << 16) + (parseInt(res[1]) << 8) + parseInt(res[2])).toString(16).slice(1);
}
function saveSettings() {
	let settings = {
		bg: getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(),
		surface: getComputedStyle(document.documentElement).getPropertyValue('--surface').trim(),
		card: getComputedStyle(document.documentElement).getPropertyValue('--card').trim(),
		accent: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
		accent2: getComputedStyle(document.documentElement).getPropertyValue('--accent2').trim(),
		text: getComputedStyle(document.documentElement).getPropertyValue('--text').trim(),
		muted: getComputedStyle(document.documentElement).getPropertyValue('--muted').trim(),
		border: getComputedStyle(document.documentElement).getPropertyValue('--border').trim(),
		green: getComputedStyle(document.documentElement).getPropertyValue('--green').trim(),
		panelHeight: filterPanel.offsetHeight
	};
	localStorage.setItem('calibre_settings', JSON.stringify(settings));
}
function loadSettings() {
	let settings = localStorage.getItem('calibre_settings');
	if (settings) {
		let s = JSON.parse(settings);
		if (s.bg) document.documentElement.style.setProperty('--bg', s.bg);
		if (s.surface) document.documentElement.style.setProperty('--surface', s.surface);
		if (s.card) document.documentElement.style.setProperty('--card', s.card);
		if (s.accent) document.documentElement.style.setProperty('--accent', s.accent);
		if (s.accent2) document.documentElement.style.setProperty('--accent2', s.accent2);
		if (s.text) document.documentElement.style.setProperty('--text', s.text);
		if (s.muted) document.documentElement.style.setProperty('--muted', s.muted);
		if (s.border) document.documentElement.style.setProperty('--border', s.border);
		if (s.green) document.documentElement.style.setProperty('--green', s.green);
		if (s.panelHeight) setPanelHeight(parseInt(s.panelHeight));
		document.getElementById('color-bg').value = rgbToHex(getComputedStyle(document.documentElement).getPropertyValue('--bg').trim());
		document.getElementById('color-card').value = rgbToHex(getComputedStyle(document.documentElement).getPropertyValue('--card').trim());
		document.getElementById('color-accent').value = rgbToHex(getComputedStyle(document.documentElement).getPropertyValue('--accent').trim());
		document.getElementById('color-text').value = rgbToHex(getComputedStyle(document.documentElement).getPropertyValue('--text').trim());
	} else {
		applyThemePreset('dark');
	}
	updateColorPreviews();
}
function resetSettings() {
	localStorage.removeItem('calibre_settings');
	applyThemePreset('dark');
	setPanelHeight(120);
}
function toggleSettings() {
	document.getElementById('settings-panel').classList.toggle('open');
}

// ========== FILTER PANEL RESIZE ==========
function onMouseMove(e) { setPanelHeight(startHeight + (e.clientY - startY)); }
function onMouseUp() {
	document.removeEventListener('mousemove', onMouseMove);
	document.removeEventListener('mouseup', onMouseUp);
	if (document.getElementById('auto-save').checked) saveSettings();
}
resizeHandle.addEventListener('mousedown', (e) => {
	e.preventDefault();
	startY = e.clientY;
	startHeight = filterPanel.offsetHeight;
	document.addEventListener('mousemove', onMouseMove);
	document.addEventListener('mouseup', onMouseUp);
});

// ========== BOOK DATA & FILTERS ==========
async function loadBooks() { const r = await fetch('/api/books'); allBooks = await r.json(); populateStaticFilters(); applyFilters(); }
function populateStaticFilters() {
	fill('f-author', [...new Set(allBooks.flatMap(b=>b.authors))].sort());
	fill('f-series', [...new Set(allBooks.filter(b=>b.series).map(b=>b.series))].sort());
	fill('f-tag', [...new Set(allBooks.flatMap(b=>b.tags))].sort());
}
function fill(id, items) {
	const sel = document.getElementById(id);
	const selected = Array.from(sel.selectedOptions).map(o=>o.value);
	sel.innerHTML = '';
	items.forEach(v => { const o = document.createElement('option'); o.value = o.textContent = v; if (selected.includes(v)) o.selected = true; sel.appendChild(o); });
}
function getSelected(sel) { return Array.from(sel.selectedOptions).map(o=>o.value); }
function updateFormatFilter() {
	const formats = [...new Set(filtered.flatMap(b=>b.formats))].sort();
	const sel = document.getElementById('f-format');
	const selected = getSelected(sel);
	sel.innerHTML = '';
	formats.forEach(f => { const o = document.createElement('option'); o.value = o.textContent = f; if (selected.includes(f)) o.selected = true; sel.appendChild(o); });
}
function applyFilters() {
	const q = document.getElementById('search-box').value.toLowerCase();
	const authors = getSelected(document.getElementById('f-author'));
	const seriesList = getSelected(document.getElementById('f-series'));
	const tags = getSelected(document.getElementById('f-tag'));
	const formats = getSelected(document.getElementById('f-format'));
	const sort = document.getElementById('f-sort').value;
	filtered = allBooks.filter(b => {
		if (authors.length && !authors.some(a=>b.authors.includes(a))) return false;
		if (seriesList.length && !seriesList.includes(b.series||'')) return false;
		if (tags.length && !tags.some(t=>b.tags.includes(t))) return false;
		if (formats.length && !formats.some(f=>b.formats.includes(f))) return false;
		if (q) { const hay = (b.title+' '+b.authors.join(' ')+' '+(b.series||'')+' '+b.tags.join(' ')).toLowerCase(); if (!hay.includes(q)) return false; }
		return true;
	});
	updateFormatFilter();
	filtered.sort((a,b) => {
		if (sort === 'author') return (a.authors[0]||'').localeCompare(b.authors[0]||'');
		if (sort === 'series') { let sc = (a.series||'zzz').localeCompare(b.series||'zzz'); return sc !== 0 ? sc : (a.series_index||0)-(b.series_index||0); }
		if (sort === 'date') return b.id - a.id;
		return a.title.localeCompare(b.title);
	});
	renderGrid(); updateDlBar();
}
function renderGrid() {
	const grid = document.getElementById('grid');
	grid.innerHTML = '';
	document.getElementById('result-count').textContent = `${filtered.length} book${filtered.length!==1?'s':''}`;
	if (filtered.length === 0) { grid.innerHTML = '<div id="empty">No books match your search.</div>'; return; }
	filtered.forEach(b => {
		const card = document.createElement('div'); card.className = 'book-card'; card.onclick = () => openModal(b);
		const coverHtml = b.has_cover ? `<img src="/cover/${b.id}" loading="lazy" alt="cover">` : `<div class="no-cover">📖</div>`;
		const seriesHtml = b.series ? `<div class="book-series">${esc(b.series)}${b.series_index!=null?` #${b.series_index}`:''}</div>` : '';
		const fmtHtml = b.formats.map(f=>`<span class="fmt-badge">${f}</span>`).join('');
		const pct = getReadPct(b);
		const progressHtml = pct > 0 ? `<div class="book-progress-wrap"><div class="book-progress-bar" style="width:${pct}%"></div></div>` : '';
		card.innerHTML = `${coverHtml}<div class="book-info"><div class="book-title">${esc(b.title)}</div><div class="book-author">${esc(b.authors[0]||'Unknown')}</div>${seriesHtml}<div class="book-formats">${fmtHtml}</div></div>${progressHtml}`;
		grid.appendChild(card);
	});
}
function getReadPct(b) {
	const epubPct = localStorage.getItem(`reader_pct_${b.id}`);
	if (epubPct) return Math.min(100, Math.max(1, parseInt(epubPct)));
	const txtPct = localStorage.getItem(`reader_pct_txt_${b.id}`);
	if (txtPct) return Math.min(100, Math.max(1, parseInt(txtPct)));
	const cbzScroll = localStorage.getItem(`reader_cbz_scroll_${b.id}`);
	if (cbzScroll) return Math.min(100, Math.max(1, parseInt(cbzScroll)));
	return 0;
}
function updateDlBar() {
	const bar = document.getElementById('dl-bar'), btn = document.getElementById('dl-collection-btn');
	const active = !!(document.getElementById('search-box').value || getSelected(document.getElementById('f-author')).length || getSelected(document.getElementById('f-series')).length || getSelected(document.getElementById('f-tag')).length || getSelected(document.getElementById('f-format')).length);
	bar.classList.toggle('visible', active && filtered.length>0);
	btn.style.display = (active && filtered.length>0) ? '' : 'none';
	document.getElementById('dl-bar-label').textContent = `${filtered.length} book${filtered.length!==1?'s':''} selected`;
}
function clearFilters() {
	document.getElementById('search-box').value = '';
	['f-author','f-series','f-tag','f-format'].forEach(id => { const sel = document.getElementById(id); Array.from(sel.options).forEach(opt => opt.selected = false); });
	applyFilters();
}
function openModal(b) {
	currentModalBook = b;
	document.getElementById('modal-title').textContent = b.title;
	document.getElementById('modal-author').textContent = b.authors.join(', ')||'Unknown';
	const seriesEl = document.getElementById('modal-series');
	if (b.series) seriesEl.innerHTML = `Series: <span onclick="filterSeries('${esc(b.series)}')">${esc(b.series)}${b.series_index!=null?` #${b.series_index}`:''}</span>`;
	else seriesEl.textContent = '';
	document.getElementById('modal-tags').innerHTML = b.tags.map(t=>`<span class="tag-pill" onclick="filterTag('${esc(t)}')">${esc(t)}</span>`).join('');
	document.getElementById('modal-desc').textContent = b.comments||'';
	document.getElementById('modal-cover').innerHTML = b.has_cover ? `<img src="/cover/${b.id}" alt="cover">` : `<div class="no-cover-lg">📖</div>`;
	let dlHtml = b.formats.map(f=>`<a href="/download/${b.id}/${f}" class="btn btn-dl btn-sm">⬇ ${f}</a>`).join('');
	dlHtml += b.formats.filter(f=>['EPUB','PDF','TXT','CBZ','CBR','MOBI'].includes(f)).map(f=>`<button class="btn btn-read btn-sm" onclick="openReaderModal(${b.id},'${f}')">📖 Read ${f}</button>`).join('');
	const pct = getReadPct(b);
	const resumeFmt = ['EPUB','TXT','CBZ','CBR','MOBI'].find(f =>
		b.formats.includes(f) && (
			localStorage.getItem(`reader_cfi_${b.id}`) ||
			localStorage.getItem(`reader_pct_txt_${b.id}`) ||
			localStorage.getItem(`reader_cbz_scroll_${b.id}`)
		)
	);
	if (pct > 0 && resumeFmt) dlHtml = `<button class="btn btn-continue btn-sm" onclick="openReaderModal(${b.id},'${resumeFmt}')">▶ Continue (${pct}%)</button>` + dlHtml;
	document.getElementById('modal-dl').innerHTML = dlHtml;
	document.getElementById('modal-bg').classList.add('open');
}
function closeModal(e) { if (!e || e.target===document.getElementById('modal-bg') || e.currentTarget.id==='modal-close') document.getElementById('modal-bg').classList.remove('open'); }
function openReaderModal(bookId, fmt) {
	const book = allBooks.find(b => b.id === bookId);
	openReader(bookId, fmt, book ? book.title : '');
}
function filterTag(tag) { closeModal(); const sel = document.getElementById('f-tag'); Array.from(sel.options).forEach(opt=>{if(opt.value===tag) opt.selected=true;}); applyFilters(); }
function filterSeries(series) { closeModal(); const sel = document.getElementById('f-series'); Array.from(sel.options).forEach(opt=>{if(opt.value===series) opt.selected=true;}); applyFilters(); }
async function downloadCollection() {
	if (filtered.length===0) return;
	document.getElementById('spinner').style.display = 'block';
	const ids = filtered.map(b=>b.id), fmtSel = document.getElementById('f-format');
	const formats = getSelected(fmtSel);
	const resp = await fetch('/download_collection', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ids, format:formats.length===1?formats[0]:''}) });
	document.getElementById('spinner').style.display = 'none';
	if (!resp.ok) { alert('Download failed.'); return; }
	const blob = await resp.blob(); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'calibre_collection.zip'; a.click(); URL.revokeObjectURL(a.href);
}
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

// ========== READER (EPUB continuous scroll, CBZ/CBR lazy load) ==========
let epubBook = null, epubRendition = null;
let readerFontSizePx = parseInt(localStorage.getItem('reader_font_size')||'16');
let currentReaderId = null;
let cbzImageUrls = [], cbzObserver = null;
let isEpubScrolled = true; // try scrolled first, fallback if needed

function hideAllViewers() {
	['pdf-viewer','txt-viewer','cbz-viewer','epub-viewer'].forEach(id => document.getElementById(id).style.display='none');
	document.getElementById('toc-btn').style.display='none';
	document.getElementById('toc-panel').classList.remove('open');
}

function getEpubTheme() {
	const s = getComputedStyle(document.documentElement);
	const bg = s.getPropertyValue('--bg').trim();
	const text = s.getPropertyValue('--text').trim();
	const accent = s.getPropertyValue('--accent2').trim();
	return {
		body: { background: bg+'!important', color: text+'!important', fontFamily: "'Segoe UI', system-ui, sans-serif!important" },
		p: { color: text+'!important', lineHeight: '1.75!important' },
		a: { color: accent+'!important' },
		'h1,h2,h3,h4': { color: text+'!important' }
	};
}

function injectThemeIntoMobi(frame) {
	try {
		const doc = frame.contentDocument || frame.contentWindow.document;
		const style = doc.createElement('style');
		const root = getComputedStyle(document.documentElement);
		const bg = root.getPropertyValue('--bg').trim();
		const text = root.getPropertyValue('--text').trim();
		const accent = root.getPropertyValue('--accent2').trim();
		style.textContent = `
			body { background: ${bg} !important; color: ${text} !important; font-family: 'Segoe UI', system-ui, sans-serif !important; }
			a { color: ${accent} !important; }
			p, div, h1, h2, h3, h4 { color: ${text} !important; }
		`;
		doc.head.appendChild(style);
	} catch(e) { console.warn("Cannot inject theme into MOBI iframe", e); }
}

async function openReader(bookId, fmt, title) {
	closeModal();
	currentReaderId = bookId;
	document.getElementById('reader-book-title').textContent = title;
	document.getElementById('reader-fmt-badge').textContent = fmt;
	document.getElementById('reader-overlay').classList.add('open');
	document.body.classList.add('no-scroll');
	document.getElementById('reader-loc').textContent = '';
	hideAllViewers();
	const url = `/read/${bookId}/${fmt}`;

	if (fmt === 'PDF') {
		const frame = document.getElementById('pdf-viewer');
		frame.src = url; frame.style.display='block';
	} else if (fmt === 'MOBI') {
		const frame = document.getElementById('pdf-viewer');
		frame.src = url; frame.style.display='block';
		frame.onload = () => injectThemeIntoMobi(frame);
	} else if (fmt === 'TXT') {
		const div = document.getElementById('txt-viewer');
		div.style.display='block'; div.style.fontSize = readerFontSizePx+'px';
		div.textContent = 'Loading…';
		const r = await fetch(url); const text = await r.text();
		div.textContent = text;
		const savedPct = localStorage.getItem(`reader_pct_txt_${bookId}`);
		if (savedPct) div.scrollTop = (parseInt(savedPct)/100) * (div.scrollHeight - div.clientHeight);
		div.onscroll = () => {
			if (!div.scrollHeight || div.scrollHeight <= div.clientHeight) return;
			const pct = Math.round(div.scrollTop / (div.scrollHeight - div.clientHeight) * 100);
			localStorage.setItem(`reader_pct_txt_${bookId}`, pct);
			document.getElementById('reader-loc').textContent = pct+'%';
		};
	} else if (fmt === 'CBZ' || fmt === 'CBR') {
		const div = document.getElementById('cbz-viewer');
		div.style.display = 'flex';
		div.innerHTML = '<div style="text-align:center;padding:2rem">Loading images…</div>';
		if (cbzObserver) cbzObserver.disconnect();
		cbzImageUrls = [];
		const r = await fetch(url); const buf = await r.arrayBuffer();
		const zip = await JSZip.loadAsync(buf);
		const imgNames = Object.keys(zip.files).filter(n=>/\.(jpg|jpeg|png|gif|webp)$/i.test(n)).sort();
		for (const name of imgNames) {
			const blob = await zip.files[name].async('blob');
			cbzImageUrls.push(URL.createObjectURL(blob));
		}
		div.innerHTML = '';
		const createImageElement = (url, idx) => {
			const img = document.createElement('img');
			img.dataset.src = url;
			img.alt = `Page ${idx+1}`;
			img.style.opacity = '0';
			img.style.transition = 'opacity 0.2s';
			img.onload = () => img.style.opacity = '1';
			return img;
		};
		const observer = new IntersectionObserver((entries) => {
			for (const entry of entries) {
				if (entry.isIntersecting) {
					const img = entry.target;
					if (img.dataset.src && !img.src) {
						img.src = img.dataset.src;
						img.removeAttribute('data-src');
					}
					observer.unobserve(img);
				}
			}
		}, { rootMargin: '200px' });
		cbzObserver = observer;
		const fragment = document.createDocumentFragment();
		for (let i = 0; i < cbzImageUrls.length; i++) {
			const img = createImageElement(cbzImageUrls[i], i);
			fragment.appendChild(img);
			observer.observe(img);
		}
		div.appendChild(fragment);
		const savedScroll = localStorage.getItem(`reader_cbz_scroll_${bookId}`);
		if (savedScroll) {
			const pct = parseInt(savedScroll);
			const maxScroll = div.scrollHeight - div.clientHeight;
			div.scrollTop = (pct / 100) * maxScroll;
		}
		div.onscroll = () => {
			if (!div.scrollHeight || div.scrollHeight <= div.clientHeight) return;
			const pct = Math.round(div.scrollTop / (div.scrollHeight - div.clientHeight) * 100);
			localStorage.setItem(`reader_cbz_scroll_${bookId}`, pct);
			document.getElementById('reader-loc').textContent = pct+'%';
		};
	} else if (fmt === 'EPUB') {
		if (typeof ePub === 'undefined') {
			document.getElementById('epub-viewer').style.display='block';
			document.getElementById('epub-area').innerHTML = `<div style="padding:2rem;color:var(--muted);text-align:center"><p>⚠️ EPUB reader library failed to load.</p><p>Check your internet connection, then reload.</p></div>`;
			return;
		}
		const epubDiv = document.getElementById('epub-viewer');
		epubDiv.style.display='block';
		document.getElementById('toc-btn').style.display='';
		const area = document.getElementById('epub-area');
		area.innerHTML = '<div style="padding:2rem;color:var(--muted);text-align:center">Loading…</div>';
		if (epubBook) { try { epubBook.destroy(); } catch(e){} }
		const epubResp = await fetch(url);
		if (!epubResp.ok) { area.innerHTML = '<div style="padding:2rem;color:var(--muted)">Failed to load EPUB.</div>'; return; }
		const epubBuf = await epubResp.arrayBuffer();
		area.innerHTML = '';
		epubBook = ePub(epubBuf);
		let flowMode = 'scrolled-doc';
		try {
			epubRendition = epubBook.renderTo(area, { width: '100%', height: '100%', flow: flowMode, spread: 'none' });
		} catch(e) {
			console.warn("scrolled-doc failed, falling back to paginated", e);
			flowMode = 'paginated';
			epubRendition = epubBook.renderTo(area, { width: '100%', height: '100%', flow: flowMode, spread: 'none' });
		}
		epubRendition.themes.register('app', getEpubTheme());
		epubRendition.themes.select('app');
		epubRendition.themes.fontSize(readerFontSizePx+'px');
		const savedCfi = localStorage.getItem(`reader_cfi_${bookId}`);
		await epubRendition.display(savedCfi || undefined);
		epubRendition.on('relocated', loc => {
			localStorage.setItem(`reader_cfi_${bookId}`, loc.start.cfi);
			try {
				const pct = Math.round(epubBook.locations.percentageFromCfi(loc.start.cfi)*100);
				document.getElementById('reader-loc').textContent = pct+'%';
				localStorage.setItem(`reader_pct_${bookId}`, pct);
				renderGrid();
			} catch(e){}
		});
		epubBook.ready
			.then(() => epubBook.locations.generate(1024))
			.then(() => { buildToc(); });
	}
}

function buildToc() {
	try {
		const toc = epubBook.navigation.toc;
		const list = document.getElementById('toc-list'); list.innerHTML = '';
		function addItems(items, depth) {
			items.forEach(item => {
				const el = document.createElement('div');
				el.className = 'toc-item' + (depth > 0 ? ' sub' : '');
				el.textContent = item.label.trim();
				el.onclick = () => { epubRendition.display(item.href); toggleToc(); };
				list.appendChild(el);
				if (item.subitems && item.subitems.length) addItems(item.subitems, depth+1);
			});
		}
		addItems(toc, 0);
	} catch(e){}
}
function toggleToc() { document.getElementById('toc-panel').classList.toggle('open'); }
function closeReader() {
	document.getElementById('reader-overlay').classList.remove('open');
	document.body.classList.remove('no-scroll');
	if (epubRendition) { try { epubBook.destroy(); } catch(e){} epubBook=null; epubRendition=null; }
	document.getElementById('pdf-viewer').src='';
	if (cbzObserver) { cbzObserver.disconnect(); cbzObserver = null; }
	if (cbzImageUrls.length) { cbzImageUrls.forEach(u => URL.revokeObjectURL(u)); cbzImageUrls = []; }
	currentReaderId = null;
	renderGrid();
}
function readerFontSize(delta) {
	readerFontSizePx = Math.max(10, Math.min(32, readerFontSizePx + delta));
	localStorage.setItem('reader_font_size', readerFontSizePx);
	const txt = document.getElementById('txt-viewer');
	if (txt.style.display!=='none') txt.style.fontSize=readerFontSizePx+'px';
	if (epubRendition) epubRendition.themes.fontSize(readerFontSizePx+'px');
}
document.addEventListener('keydown', e=>{
	const readerOpen = document.getElementById('reader-overlay').classList.contains('open');
	if (e.key==='Escape') { readerOpen ? closeReader() : closeModal(); return; }
});
document.getElementById('search-box').addEventListener('input', applyFilters);
loadSettings();
setPanelHeight(filterPanel.offsetHeight);
loadBooks();
</script>
</body>
</html>
"""


# ========== FLASK APP INIT ==========

app = Flask(__name__)
LIBRARY_PATH: Path = None
SUPPORTED_FORMATS = {"EPUB","PDF","MOBI","TXT","CBZ","CBR","AZW","AZW3","LIT","DJVU"}


# ========== DATABASE HELPERS ==========

def get_db():
    db_path = LIBRARY_PATH / "metadata.db"
    if not db_path.exists():
        raise FileNotFoundError(f"metadata.db not found at {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def fetch_all_books():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT b.id,b.title,b.path,b.has_cover,b.timestamp,b.series_index FROM books b ORDER BY b.sort")
    books_raw = cur.fetchall()
    cur.execute("SELECT bal.book, a.name FROM books_authors_link bal JOIN authors a ON a.id=bal.author")
    author_map = {}
    for row in cur.fetchall():
        author_map.setdefault(row[0], []).append(row[1])
    cur.execute("SELECT btl.book, t.name FROM books_tags_link btl JOIN tags t ON t.id=btl.tag")
    tag_map = {}
    for row in cur.fetchall():
        tag_map.setdefault(row[0], []).append(row[1])
    cur.execute("SELECT bsl.book, s.name FROM books_series_link bsl JOIN series s ON s.id=bsl.series")
    series_map = {row[0]: row[1] for row in cur.fetchall()}
    cur.execute("SELECT book, format, name FROM data")
    fmt_map, file_map = {}, {}
    for row in cur.fetchall():
        fmt = row[1].upper()
        if fmt in SUPPORTED_FORMATS:
            fmt_map.setdefault(row[0], []).append(fmt)
            file_map[(row[0], fmt)] = row[2]
    cur.execute("SELECT book, text FROM comments")
    comment_map = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    books = []
    for b in books_raw:
        bid = b["id"]
        books.append({
            "id": bid, "title": b["title"], "path": b["path"], "has_cover": bool(b["has_cover"]),
            "authors": author_map.get(bid, []), "tags": tag_map.get(bid, []),
            "series": series_map.get(bid), "series_index": b["series_index"],
            "formats": sorted(fmt_map.get(bid, [])), "comments": comment_map.get(bid, "")
        })
    return books, file_map


# ========== ROUTES ==========

@app.route("/")
def index():
    return render_template_string(TEMPLATE)


@app.route("/api/books")
def api_books():
    books, _ = fetch_all_books()
    return jsonify([{k:v for k,v in b.items() if k!="path"} for b in books])


@app.route("/cover/<int:book_id>")
def cover(book_id):
    books, _ = fetch_all_books()
    book = next((b for b in books if b["id"]==book_id), None)
    if not book or not book["has_cover"]:
        abort(404)
    cover_path = LIBRARY_PATH / book["path"] / "cover.jpg"
    return send_file(str(cover_path), mimetype="image/jpeg") if cover_path.exists() else abort(404)


READER_MIME = {
    "EPUB": "application/epub+zip",
    "PDF":  "application/pdf",
    "TXT":  "text/plain; charset=utf-8",
    "CBZ":  "application/zip",
    "CBR":  "application/zip",
    "MOBI": "text/html; charset=utf-8",
}
READABLE_FORMATS = set(READER_MIME.keys())


# ========== CBR CONVERSION ==========

def _cbr_to_zip(filepath):
    try:
        import rarfile
    except ImportError:
        return None, "rarfile not installed – run:  pip install rarfile"
    try:
        buf = io.BytesIO()
        with rarfile.RarFile(str(filepath)) as rf:
            names = sorted(n for n in rf.namelist()
                        if re.search(r'\.(jpe?g|png|gif|webp)$', n, re.I))
            if not names:
                return None, "No image files found inside the CBR archive."
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
                for name in names:
                    zf.writestr(name, rf.read(name))
        buf.seek(0)
        return buf, None
    except Exception as exc:
        return None, str(exc)


# ========== MOBI CONVERSION (returns clean HTML, theme injected client-side) ==========

def _mobi_to_html(filepath):
    try:
        import mobi
    except ImportError:
        return None, "mobi library not installed – run: pip install mobi"
    temp_dir = None
    try:
        temp_dir, extracted_file_path = mobi.extract(str(filepath))
        if not extracted_file_path or not Path(extracted_file_path).exists():
            return None, "MOBI extraction failed: No output file was created."
        raw_bytes = Path(extracted_file_path).read_bytes()
        try:
            html_content = raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            html_content = raw_bytes.decode('latin-1')
            html_content = re.sub(r'Â\s', ' ', html_content)
            html_content = re.sub(r'Â ', ' ', html_content)
            html_content = html_content.replace('Â', '')
        base_dir = Path(extracted_file_path).parent
        def _inline_images(match):
            src = match.group(1)
            if src.startswith(("data:", "http://", "https://")):
                return match.group(0)
            img_path = base_dir / src
            if not img_path.exists():
                img_path = base_dir / Path(src).name
            if img_path.exists():
                ext = img_path.suffix.lower().lstrip(".")
                mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "octet-stream")
                data = base64.b64encode(img_path.read_bytes()).decode()
                return f'src="data:image/{mime};base64,{data}"'
            return match.group(0)
        html_content = re.sub(r'src="([^"]*)"', _inline_images, html_content)
        # Remove any existing style/head to avoid conflicts, theme will be added by client
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        if not re.search(r'<head', html_content, re.I):
            html_content = f"<head><meta charset='utf-8'></head>{html_content}"
        return html_content, None
    except Exception as exc:
        return None, str(exc)
    finally:
        if temp_dir and Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


# ========== READ ROUTE ==========

@app.route("/read/<int:book_id>/<fmt>")
def read_book(book_id, fmt):
    fmt = fmt.upper()
    if fmt not in READABLE_FORMATS:
        abort(415)
    books, file_map = fetch_all_books()
    book = next((b for b in books if b["id"] == book_id), None)
    if not book:
        abort(404)
    stem = file_map.get((book_id, fmt))
    if not stem:
        abort(404)
    filepath = LIBRARY_PATH / book["path"] / f"{stem}.{fmt.lower()}"
    if not filepath.exists():
        abort(404)
    if fmt == "CBR":
        buf, err = _cbr_to_zip(filepath)
        if err:
            return f"<pre>CBR error: {err}</pre>", 500
        return send_file(buf, mimetype="application/zip", as_attachment=False)
    if fmt == "MOBI":
        html, err = _mobi_to_html(filepath)
        if err:
            return (f"<!doctype html><html><body style='background:#0f1117;color:#e2e8f0;"
                    f"font-family:sans-serif;padding:2rem'>"
                    f"<h2>⚠️ MOBI error</h2><pre>{err}</pre></body></html>"), 500
        from flask import Response
        return Response(html, mimetype="text/html; charset=utf-8")
    return send_file(str(filepath), mimetype=READER_MIME[fmt], as_attachment=False)


# ========== DOWNLOAD ROUTES ==========

@app.route("/download/<int:book_id>/<fmt>")
def download_book(book_id, fmt):
    fmt = fmt.upper()
    books, file_map = fetch_all_books()
    book = next((b for b in books if b["id"]==book_id), None)
    if not book:
        abort(404)
    stem = file_map.get((book_id, fmt))
    if not stem:
        abort(404)
    filepath = LIBRARY_PATH / book["path"] / f"{stem}.{fmt.lower()}"
    return send_from_directory(str(filepath.parent), filepath.name, as_attachment=True, download_name=f"{stem}.{fmt.lower()}".replace("/","_")) if filepath.exists() else abort(404)


@app.route("/download_collection", methods=["POST"])
def download_collection():
    data = request.get_json(force=True)
    ids = set(data.get("ids", []))
    fmt_filter = data.get("format", "").upper()
    books, file_map = fetch_all_books()
    selected = [b for b in books if b["id"] in ids]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for book in selected:
            formats = [f for f in book["formats"] if not fmt_filter or f==fmt_filter]
            for fmt in formats:
                stem = file_map.get((book["id"], fmt))
                if not stem:
                    continue
                filepath = LIBRARY_PATH / book["path"] / f"{stem}.{fmt.lower()}"
                if not filepath.exists():
                    continue
                author_safe = (book["authors"][0] if book["authors"] else "Unknown").replace("/","_")
                title_safe = book["title"].replace("/","_")[:80]
                zf.write(str(filepath), f"{author_safe}/{title_safe}.{fmt.lower()}")
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="calibre_collection.zip")


# ========== MAIN ENTRY POINT ==========

def main():
    parser = argparse.ArgumentParser(description="Calibre Library Web Server")
    parser.add_argument("--library", default="./", help="Path to Calibre library folder default to current folder.(./)")
    parser.add_argument("--port", type=int, default=5000, help="Default port to 5000")
    parser.add_argument("--host", default="0.0.0.0", help="Default to full open at http://0.0.0.0")
    parser.add_argument("--browser", action="store_true", help="Open a browser tab automatically (default is not to open)")
    args = parser.parse_args()
    global LIBRARY_PATH
    LIBRARY_PATH = Path(args.library).expanduser().resolve()
    if not (LIBRARY_PATH / "metadata.db").exists():
        print(f"❌ metadata.db not found in {LIBRARY_PATH}")
        raise SystemExit(1)
    print(f"📚 Serving library: {LIBRARY_PATH}")
    print(f"🌐 Open http://{'localhost' if args.host=='0.0.0.0' else args.host}:{args.port}")
    try: import rarfile; print("✅ rarfile found  – CBR reading enabled")
    except ImportError: print("ℹ️  pip install rarfile   → enables in-browser CBR reading")
    try: import mobi;    print("✅ mobi found     – MOBI reading enabled")
    except ImportError: print("ℹ️  pip install mobi      → enables in-browser MOBI reading")
    if args.browser:
        import threading, webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()
    from waitress import serve
    serve(app, host=args.host, port=args.port, threads=8)


if __name__ == "__main__":
    main()