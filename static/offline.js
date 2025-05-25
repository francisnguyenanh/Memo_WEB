importScripts('https://unpkg.com/idb@7/build/umd.js');

const DB_NAME = 'memoApp';
const STORE_NAME = 'notes';

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
    }
}

self.addEventListener('sync', event => {
    if (event.tag === 'sync-notes') {
        event.waitUntil(syncNotes());
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const forms = document.querySelectorAll('form[method="POST"]');
    forms.forEach(form => {
        form.addEventListener('submit', async event => {
            if (!navigator.onLine) {
                event.preventDefault();
                const formData = new FormData(form);
                const note = {
                    title: formData.get('title') || '',
                    content: formData.get('content') || '',
                    tags: formData.get('tags') || null,
                    category_id: formData.get('category_id') ? parseInt(formData.get('category_id')) : null,
                    due_date: formData.get('due_date') || null,
                    is_completed: formData.get('is_completed') === 'on'
                };
                await saveNoteOffline(note);
                alert('Note saved offline. It will sync when online.');
                window.location.href = '/';
            }
        });
    });
});