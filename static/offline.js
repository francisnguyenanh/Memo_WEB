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
                    category_id: formData.get('category_id') ? parseInt(formData.get('category_id')) : null,
                    due_date: formData.get('due_date') || null,
                    is_completed: formData.get('is_completed') === 'on'
                };
                // Notify Service Worker to save note
                if ('serviceWorker' in navigator) {
                    navigator.serviceWorker.controller.postMessage({
                        type: 'SAVE_NOTE',
                        note: note
                    });
                    alert('Note saved offline. It will sync when online.');
                    window.location.href = '/';
                }
            }
        });
    });
});

// Listen for messages from Service Worker
navigator.serviceWorker.addEventListener('message', event => {
    if (event.data.type === 'SYNC_COMPLETE') {
        console.log('Notes synced successfully');
    }
});