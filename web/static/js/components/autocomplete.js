// === components/autocomplete.js ===
function setupAutocomplete(inputId, listId, endpoint, onSelect) {
    const input = document.getElementById(inputId);
    const list = document.getElementById(listId);
    const status = document.getElementById('cidade-status');
    if (!input || !list) return;
    input.setAttribute('role', input.getAttribute('role') || 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', list.id || listId);
    input.setAttribute('aria-expanded', 'false');
    list.setAttribute('role', list.getAttribute('role') || 'listbox');

    let timer = null;
    let highlightedIndex = -1;
    let suggestions = [];
    let selectedValue = '';

    const clearList = () => {
        list.innerHTML = '';
        list.classList.remove('open');
        highlightedIndex = -1;
        input.setAttribute('aria-expanded', 'false');
        input.removeAttribute('aria-activedescendant');
    };

    const renderSuggestions = () => {
        list.innerHTML = '';
        if (!suggestions.length) {
            clearList();
            status && (status.textContent = 'Nenhuma cidade encontrada para esse trecho.');
            return;
        }

        suggestions.forEach((item, index) => {
            const li = document.createElement('li');
            const optionId = `${listId}-option-${index}`;
            li.id = optionId;
            li.textContent = item;
            li.className = 'ac-item';
            li.setAttribute('role', 'option');
            li.setAttribute('aria-selected', index === highlightedIndex ? 'true' : 'false');
            li.addEventListener('mousedown', (event) => {
                event.preventDefault();
                commitSelection(item);
            });
            if (index === highlightedIndex) {
                li.classList.add('selected');
                input.setAttribute('aria-activedescendant', optionId);
            }
            list.appendChild(li);
        });
        list.classList.add('open');
        input.setAttribute('aria-expanded', 'true');
    };

    const commitSelection = (value) => {
        selectedValue = value;
        input.value = value;
        clearList();
        if (status) status.textContent = `Abrindo relatorio de ${value}...`;
        onSelect(value);
    };

    input.addEventListener('input', () => {
        clearTimeout(timer);
        const query = input.value.trim();
        if (query !== selectedValue && status) status.textContent = 'Selecione uma cidade da lista para continuar.';
        selectedValue = '';
        if (query.length < 2) {
            clearList();
            return;
        }
        timer = setTimeout(async () => {
            try {
                const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`);
                suggestions = await response.json();
                highlightedIndex = suggestions.length ? 0 : -1;
                renderSuggestions();
            } catch {
                clearList();
            }
        }, 180);
    });

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            if (highlightedIndex >= 0 && suggestions[highlightedIndex]) {
                commitSelection(suggestions[highlightedIndex]);
            }
            return;
        }

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            if (!suggestions.length) return;
            highlightedIndex = Math.min(highlightedIndex + 1, suggestions.length - 1);
            renderSuggestions();
        }

        if (event.key === 'ArrowUp') {
            event.preventDefault();
            if (!suggestions.length) return;
            highlightedIndex = Math.max(highlightedIndex - 1, 0);
            renderSuggestions();
        }

        if (event.key === 'Escape') {
            clearList();
        }
    });

    input.addEventListener('blur', () => {
        window.setTimeout(() => {
            clearList();
        }, 120);
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.autocomplete-wrap')) clearList();
    });
}

function initCidadeAutocomplete() {
    setupAutocomplete('ac-cidade', 'aclist-cidade', '/api/autocomplete/municipio', (value) => {
        window.location.href = `/search/cidade?q=${encodeURIComponent(value)}`;
    });
}

