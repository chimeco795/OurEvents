document.addEventListener('DOMContentLoaded', function () {
    function updateCharCounter(input, counterId, progressId) {
        const maxLength = input.maxLength;
        const currentLength = input.value.length;
        const remainingChars = maxLength - currentLength;

        // Actualiza el contador de caracteres
        document.getElementById(counterId).textContent = `${remainingChars} / ${maxLength}`;

        // Actualiza la barra de progreso
        const progressBar = document.getElementById(progressId);
        progressBar.style.width = `${(currentLength / maxLength) * 100}%`;
        progressBar.classList.add('progress-bar-striped');
        if (currentLength === 0) {
            progressBar.classList.remove('bg-success', 'bg-warning', 'bg-danger');
        } else if (remainingChars < 10) {
            progressBar.classList.add('bg-danger');
        } else if (remainingChars < 20) {
            progressBar.classList.add('bg-warning');
        } else {
            progressBar.classList.add('bg-success');
        }
    }

    document.getElementById('titulo').addEventListener('input', function () {
        updateCharCounter(this, 'titulo-counter', 'titulo-progress');
    });

    document.getElementById('nombre').addEventListener('input', function () {
        updateCharCounter(this, 'nombre-counter', 'nombre-progress');
    });

    document.getElementById('comentario').addEventListener('input', function () {
        updateCharCounter(this, 'comentario-counter', 'comentario-progress');
    });
});
