importScripts('https://unpkg.com/idb@7/build/umd.js');

const CACHE_NAME = 'memo-app-v1';
const DB_NAME = 'memoApp';
const STORE_NAME = 'notes';

const urlsToCache = [
    '/',
    '/static/offline.js',
    '/templates/index.html',
    '/templates/add_note.html',
    '/templates/edit_note.html',
    '/templates/login.html',
    '/templates/import_note.html',
    '/templates/share_note.html',
    '/templates/add_category.html',
    '/templates/edit_category.html',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons/font/bootstrap-icons.css'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(urlsToCache);
        })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});

async function initDB() {
    return idb.openDB(DB_NAME, 1, {
        upgrade(db) {
            db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
        }
    });
}

async function saveNoteOffline(note) {
    const db = await initDB();
    await db.put(STORE_NAME, note);
}

async function getOfflineNotes() {
    const db = await initDB();
    return db.getAll(STORE_NAME);
}

async function syncNotes() {
    const notes = await getOfflineNotes();
    if (notes.length > 0) {
        try {
            const response = await fetch('/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ notes })
            });
            if (response.ok) {
                const db = await initDB();
                await db.clear(STORE_NAME);
                const updatedNotes = await response.json();
                for (const note of updatedNotes.notes) {
                    await db.put(STORE_NAME, note);
                }
            }
        } catch (error) {
            console.error('Sync failed:', error);
        }
    }
}

self.addEventListener('sync', event => {
    if (event.tag === 'sync-notes') {
        event.waitUntil(syncNotes());
    }
});