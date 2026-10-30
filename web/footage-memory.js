/* Remembers the footage of the current project between visits, in this browser only.
   - Every file: name, size and, once uploaded, the server path, so a reload does not
     lose finished uploads.
   - Chrome/Edge desktop: also a read-only handle to the original on the person's disk,
     wherever it lives, so an interrupted upload resumes without dropping the file again.
   Local paths never leave the browser; the server only sees uploaded bytes. */
const footageMemory = (() => {
  const DB = 'montara-footage', STORE = 'files', MAX_AGE_MS = 14 * 24 * 3600 * 1000;
  let opening = null;
  const open = () => opening ||= new Promise((resolve, reject) => {
    const request = indexedDB.open(DB, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, {keyPath: 'id'});
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  async function run(mode, action) {
    try {
      const db = await open();
      return await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, mode);
        const request = action(tx.objectStore(STORE));
        let result;
        if (request) request.onsuccess = () => { result = request.result; };
        tx.oncomplete = () => resolve(result);
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error);
      });
    } catch (error) {
      console.warn('Footage memory unavailable', error);  // private windows, blocked storage
      return undefined;
    }
  }
  const dropHandles = typeof DataTransferItem !== 'undefined' && 'getAsFileSystemHandle' in DataTransferItem.prototype;
  return {
    pickerAvailable: typeof window.showOpenFilePicker === 'function',
    /* Call synchronously inside the drop event: the items expire afterwards. */
    handlesFromDrop(dataTransfer) {
      if (!dropHandles) return Promise.resolve([]);
      const pending = [...dataTransfer.items].filter(item => item.kind === 'file')
        .map(item => item.getAsFileSystemHandle().catch(() => null));
      return Promise.all(pending).then(list => list.filter(handle => handle && handle.kind === 'file'));
    },
    async pick(kind) {
      const accept = kind === 'audio'
        ? {'audio/*': ['.wav', '.mp3', '.m4a', '.aif', '.aiff', '.flac', '.ogg']}
        : {'video/*': ['.mp4', '.mov', '.mts', '.m4v', '.mkv', '.webm', '.avi']};
      const handles = await window.showOpenFilePicker({multiple: true, types: [{description: kind === 'audio' ? 'Audio' : 'Video', accept}]});
      return {handles, files: await Promise.all(handles.map(handle => handle.getFile()))};
    },
    save(record) { return run('readwrite', store => store.put({...record, savedAt: Date.now()})); },
    forget(id) { return run('readwrite', store => store.delete(id)); },
    async list(platform) {
      const all = (await run('readonly', store => store.getAll())) || [];
      const fresh = all.filter(record => Date.now() - (record.savedAt || 0) < MAX_AGE_MS);
      all.filter(record => !fresh.includes(record)).forEach(record => this.forget(record.id));
      return fresh.filter(record => record.platform === platform);
    },
    async clear(platform) {
      for (const record of await this.list(platform)) await this.forget(record.id);
    },
    /* Returns the File again if the person allows it and it did not change since. */
    async reopen(record) {
      const handle = record.handle;
      if (!handle) return null;
      let permission = await handle.queryPermission({mode: 'read'});
      if (permission !== 'granted') permission = await handle.requestPermission({mode: 'read'});
      if (permission !== 'granted') return null;
      const file = await handle.getFile();
      return file.size === record.size && file.lastModified === record.lastModified ? file : null;
    },
  };
})();
