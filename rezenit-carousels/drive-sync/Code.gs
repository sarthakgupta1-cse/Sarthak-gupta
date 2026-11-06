/**
 * RezenIt carousel -> Google Drive sync.
 *
 * Copies every carousel folder from the GitHub repo into the Drive folder below:
 *   <Person>/<DD-MM-YY> Carousel <n>/1.png ... 6.png   (Person = Shalini, Tanmay, Yash)
 * Safe to run any number of times: folders/files that already exist are skipped.
 *
 * It reads carousels/manifest.json and downloads files from raw.githubusercontent.com,
 * so it never touches the GitHub REST API (whose anonymous limit Apps Script's shared
 * servers exhaust quickly).
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
  const manifest = JSON.parse(fetch_(`${CONFIG.PATH}/manifest.json?t=${Date.now()}`).getContentText());
  let added = 0;
  for (const entry of manifest.folders) {
    if (!NAME_RE.test(entry.name)) continue;
    // entry.owner = person folder ("Shalini", "Tanmay", "Yash"); empty for older root-level days
    const parent = entry.owner ? getOrCreate_(root, entry.owner) : root;
    const folder = getOrCreate_(parent, entry.name);
    for (const file of entry.files) {
      if (folder.getFilesByName(file).hasNext()) continue;
      const dir = entry.owner ? `${entry.owner}/${entry.name}` : entry.name;
      const blob = fetch_(`${CONFIG.PATH}/${dir}/${file}`).getBlob().setName(file);
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

function fetch_(path) {
  const [p, q] = path.split('?');
  const url = `https://raw.githubusercontent.com/${CONFIG.OWNER}/${CONFIG.REPO}/refs/heads/${CONFIG.BRANCH}/` +
    p.split('/').map(encodeURIComponent).join('/') + (q ? `?${q}` : '');
  const res = UrlFetchApp.fetch(url, { headers: authHeaders_(), muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error(`GitHub ${res.getResponseCode()} for ${url}`);
  return res;
}

// Only needed if the repo is private: Project Settings > Script properties > GITHUB_TOKEN
// (a fine-grained token with read-only "Contents" access to this one repo).
function authHeaders_() {
  const t = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  return t ? { Authorization: `Bearer ${t}` } : {};
}

function getOrCreate_(parent, name) { const it = parent.getFoldersByName(name); return it.hasNext() ? it.next() : parent.createFolder(name); }
