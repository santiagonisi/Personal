// Funciones globales para AJAX
const API_BASE = '/api';

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.textContent = message;
    document.body.insertBefore(notification, document.body.firstChild);
    
    setTimeout(() => notification.remove(), 3000);
}

async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        }
    };
    
    if (data && (method === 'POST' || method === 'PUT')) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(endpoint, options);
        if (!response.ok) {
            let errorMessage = `HTTP error! status: ${response.status}`;
            try {
                const errorPayload = await response.json();
                if (errorPayload && errorPayload.error) {
                    errorMessage = errorPayload.error;
                }
            } catch (_) {
            }
            throw new Error(errorMessage);
        }
        return await response.json();
    } catch (error) {
        console.error('Error:', error);
        showNotification(error.message || 'Error en la solicitud', 'error');
        throw error;
    }
}

// Cargar datos en tabla
async function loadTable(endpoint, tableSelector) {
    try {
        const data = await apiCall(endpoint);
        const table = document.querySelector(tableSelector);
        if (table) {
            table.innerHTML = '';
            data.forEach(item => {
                const row = document.createElement('tr');
                row.innerHTML = `<td>${JSON.stringify(item)}</td>`;
                table.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Error loading table:', error);
    }
}

// Formatear fecha
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('es-AR');
}

// Formatear fecha para input date (YYYY-MM-DD sin problemas de zona horaria)
function formatDateForInput(dateString) {
    if (!dateString) return '';
    // Si es string en formato YYYY-MM-DD, devolverlo tal cual
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
        return dateString;
    }
    // Si es un formato diferente, convertir
    const date = new Date(dateString + 'T00:00:00');
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// Formatear hora
function formatTime(timeString) {
    if (!timeString) return '';
    return timeString.substring(0, 5);
}
