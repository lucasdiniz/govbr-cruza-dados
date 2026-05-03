// === components/dialog-table-sort.js ===
function _initDialogTableSort(root) {
    root.querySelectorAll('.dialog-table').forEach(table => {
        const headers = Array.from(table.querySelectorAll('thead th'));
        let sortCol = -1, sortAsc = true;
        headers.forEach((th, colIndex) => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => {
                if (sortCol === colIndex) { sortAsc = !sortAsc; } else { sortCol = colIndex; sortAsc = true; }
                headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
                th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                rows.sort((a, b) => {
                    const cellElA = a.children[colIndex];
                    const cellElB = b.children[colIndex];
                    const cellA = cellElA?.textContent.trim() || '';
                    const cellB = cellElB?.textContent.trim() || '';
                    const numA = _sortNumber(cellElA);
                    const numB = _sortNumber(cellElB);
                    if (!isNaN(numA) && !isNaN(numB)) return sortAsc ? numA - numB : numB - numA;
                    return sortAsc ? cellA.localeCompare(cellB, 'pt-BR') : cellB.localeCompare(cellA, 'pt-BR');
                });
                rows.forEach(r => tbody.appendChild(r));
            });
        });
    });
}

