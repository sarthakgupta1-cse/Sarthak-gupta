/**
 * RezenIt carousel -> Google Drive sync.
 *
 * Copies every "<DD-MM-YY> Carousel <n>" folder from the GitHub repo into the
 * Drive folder below, as "<DD-MM-YY> Carousel <n>/1.png ... 6.png".
 * Safe to run any number of times: folders/files that already exist are skipped.
 *
 * Setup: paste into script.google.com, run `setup` once, approve the permissions.
 */
const CONFIG = {
  OWNER: 'sarthakgupta1-cse',
  REPO: 'Sarthak-gupta',
  BRANCH: 'claude/brave-davinci-pbopjl',
  PATH: 'rezenit-carousels/carousels',
  DRIVE_FOLDER_ID: '1Jb5AKe1BpI15Kb4NYMPf9ulE-6iC3tl5', // "Rezenit TikTok Carousel"
};
const NAME_RE = /^\d{2}-\d{2}-\d{2} Carousel \d+$/;

function syncCarousels() {
  const root = DriveApp.getFolderById(CONFIG.DRIVE_FOLDER_ID);
  const dirs = githubList_(CONFIG.PATH).filter(e => e.type === 'dir' && NAME_RE.test(e.name));
  let added = 0;
  for (const dir of dirs) {
    let folder = firstOrNull_(root.getFoldersByName(dir.name));
    if (folder && countFiles_(folder) >= 6) continue; // already complete, no GitHub call needed
    if (!folder) folder = root.createFolder(dir.name);
    const files = githubList_(dir.path).filter(e => e.type === 'file' && /\.png$/i.test(e.name));
    for (const f of files) {
      if (folder.getFilesByName(f.name).hasNext()) continue;
      const blob = UrlFetchApp.fetch(f.download_url, { headers: authHeaders_() }).getBlob().setName(f.name);
      folder.createFile(blob);
      added++;
    }
  }
  console.log(`Sync done: ${added} new image(s).`);
}

/** Run once: does a first sync and installs an hourly trigger. */
function setup() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'syncCarousels')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('syncCarousels').timeBased().everyHours(1).create();
  syncCarousels();
}

function githubList_(path) {
  const url = `https://api.github.com/repos/${CONFIG.OWNER}/${CONFIG.REPO}/contents/${encodeURI(path)}?ref=${encodeURIComponent(CONFIG.BRANCH)}`;
  const res = UrlFetchApp.fetch(url, {
    headers: Object.assign({ Accept: 'application/vnd.github+json' }, authHeaders_()),
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() === 404) return []; // nothing published yet
  if (res.getResponseCode() !== 200) throw new Error(`GitHub ${res.getResponseCode()}: ${res.getContentText().slice(0, 300)}`);
  return JSON.parse(res.getContentText());
}

// Only needed if the repo is private: Project Settings > Script properties > GITHUB_TOKEN
// (a fine-grained token with read-only "Contents" access to this one repo).
function authHeaders_() {
  const t = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  return t ? { Authorization: `Bearer ${t}` } : {};
}

function firstOrNull_(it) { return it.hasNext() ? it.next() : null; }
function countFiles_(folder) { let n = 0; const it = folder.getFiles(); while (it.hasNext()) { it.next(); n++; } return n; }
