// Show the "add item" form in place of its button, or put the button back
function toggleGiftForm() {
    const form = document.getElementById('giftForm');
    const button = document.getElementById('toggleButton');
    form.hidden = !form.hidden;
    button.hidden = !form.hidden;
}

// Swap an item card between its normal view and its edit form
function toggleEdit(itemId) {
    for (const id of ['view-' + itemId, 'edit-' + itemId]) {
        const el = document.getElementById(id);
        el.hidden = !el.hidden;
    }
}
