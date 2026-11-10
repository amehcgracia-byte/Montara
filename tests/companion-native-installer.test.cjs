const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {spawnSync}=require('node:child_process');
const web=fs.readFileSync('web/index.html','utf8');
const app=fs.readFileSync('app.py','utf8');
const installer=fs.readFileSync('companion/macos-installer/postinstall.in','utf8');
const updater=fs.readFileSync('companion/install.sh','utf8');
const client=fs.readFileSync('web/montara.js','utf8');

test('Companion download is a single native pkg, never a ZIP/script bundle',()=>{
  const start=app.indexOf('@app.get("/montara/companion/download")');
  const end=app.indexOf('_apply_branding(',start);
  const code=app.slice(start,end);
  assert.match(code,/\.pkg/);
  assert.match(code,/send_file\(package/);
  assert.doesNotMatch(code,/zipfile|ZipFile|\.zip/);
  assert.match(web,/Download Companion installer \(\.pkg\)/);
  assert.doesNotMatch(web,/open the zip|Unzip the download/);
  assert.doesNotMatch(client,/Unzip the download and open Install/);
});
test('Native installer runs pinned video updater as logged-in user, not root',()=>{
  assert.match(installer,/stat -f '%Su' \/dev\/console/);
  assert.match(installer,/launchctl asuser/);
  assert.match(installer,/sudo -H -u/);
  assert.match(installer,/--video/);
  assert.match(installer,/MONTARA_INSTALL_ONLY=1/);
  assert.match(installer,/Library\/LaunchAgents/);
  assert.match(installer,/launchctl bootstrap/);
  assert.doesNotMatch(installer,/launchctl kickstart -k/);
  assert.match(installer,/verified.*ENGINE_COMMIT/);
  assert.match(installer,/exit 1/);
  assert.match(installer,/__ENGINE_COMMIT__/);
  assert.match(installer,/__MONTARA_COMMIT__/);
});
test('Installer refuses to stop an active Companion render',()=>{
  assert.match(updater,/\.get\("busy"\)/);
  assert.match(updater,/A Companion job is active/);
  assert.match(updater,/pgrep -P "\$listener"/);
});
test('Installer scripts pass shell parser',()=>{
  for(const file of ['companion/macos-installer/postinstall.in','companion/macos-installer/build.sh','companion/install.sh']){
    const result=spawnSync('bash',['-n',file],{encoding:'utf8'});
    assert.equal(result.status,0, file+': '+result.stderr);
  }
});

test('Installer scripts are readable after dropping privileges and failures are logged',()=>{
  assert.match(installer,/mktemp -d \/private\/tmp\/montara-companion-install/);
  assert.match(installer,/chmod 755 "\$STAGE"/);
  assert.match(installer,/cp "\$HERE\/install\.sh" "\$STAGE\/install\.sh"/);
  assert.match(installer,/chown root:wheel "\$STAGE\/install\.sh"/);
  assert.match(installer,/bash "\$STAGE\/install\.sh" --video/);
  assert.match(installer,/installer\.log/);
  assert.match(installer,/tee -a "\$LOG_FILE"/);
});

test('An already-running matching Companion must not be launched again',()=>{
  assert.match(installer,/verified.*ENGINE_COMMIT.*managed/);
  assert.match(installer,/Not starting another Companion/);
  assert.doesNotMatch(installer,/launchctl kickstart -k/);
  assert.match(installer,/<key>KeepAlive<\/key><false\/>/);
});
test('A stale listener can only be stopped if idle and owned by the installing user',()=>{
  assert.match(installer,/d\["busy"\] is False/);
  assert.match(installer,/pgrep -P "\$pid"/);
  assert.match(installer,/-sTCP:ESTABLISHED/);
  assert.match(installer,/\$owner" != "\$CONSOLE_USER"/);
  assert.match(installer,/Port 47820 belongs to another process/);
  assert.match(installer,/run_as_owner kill -TERM/);
  assert.match(installer,/Old Companion did not stop/);
});

test('The previous KeepAlive agent is unloaded before touching installed files',()=>{
  const unload=installer.indexOf('run_as_owner launchctl bootout "gui/$UID_FOR_USER/website.montara.companion"');
  const install=installer.indexOf('bash "$STAGE/install.sh" --video');
  assert.ok(unload>0 && install>unload);
  assert.match(installer,/Finish local jobs before updating/);
});
