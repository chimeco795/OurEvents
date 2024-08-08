document.addEventListener('DOMContentLoaded', function () {
    function updateProgress(input, progressId, maxLength) {
        var length = input.value.length;
        var progress = (length / maxLength) * 100;
        document.getElementById(progressId).style.width = progress + '%';
    }

    var nombreInput = document.getElementById('nombre');
    nombreInput.addEventListener('input', function () {
        updateProgress(this, 'nombre-progress', 25);
    });

    var asuntoInput = document.getElementById('asunto');
    asuntoInput.addEventListener('input', function () {
        updateProgress(this, 'asunto-progress', 35);
    });

    var mensajeInput = document.getElementById('mensaje');
    mensajeInput.addEventListener('input', function () {
        updateProgress(this, 'mensaje-progress', 300);
    });

    // Validación más flexible del campo de teléfono
    var telefonoInput = document.getElementById('telefono');
    telefonoInput.addEventListener('input', function () {
        var pattern = /^[0-9]{8,10}$/;
        if (!pattern.test(this.value)) {
            this.setCustomValidity("El teléfono debe tener entre 8 y 10 dígitos sin caracteres especiales.");
        } else {
            this.setCustomValidity("");
        }
    });

    // Cambia el color del ícono de WhatsApp al marcar la casilla
    var whatsappCheckbox = document.getElementById('whatsapp');
    whatsappCheckbox.addEventListener('change', function () {
        var whatsappIcon = document.querySelector('.form-check-label i');
        if (this.checked) {
            whatsappIcon.style.color = '#25d366'; // Verde WhatsApp
        } else {
            whatsappIcon.style.color = '#6c757d'; // Gris original
        }
    });
});
