// ...existing code...
window.addEventListener('resize', adjustOutputBoxes);

function adjustOutputBoxes() {
    const logOutput = document.getElementById('log-output');
    const technicalOutput = document.getElementById('technical-output');
    const windowHeight = window.innerHeight;
    
    logOutput.style.height = (windowHeight * 0.3) + 'px';
    technicalOutput.style.height = (windowHeight * 0.6) + 'px';
}

adjustOutputBoxes();
// ...existing code...
