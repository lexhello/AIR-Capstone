function showMessage() {
    document.getElementById('message').innerText = 'Hello from JavaScript!';
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded and parsed');

    const soundButton = document.getElementById('soundButton');
    const clickSound = document.getElementById('clickSound');

    console.log('soundButton:', soundButton);
    console.log('clickSound:', clickSound);

    if (soundButton && clickSound) {
        soundButton.addEventListener('click', () => {
            console.log('Button clicked — attempting to play sound');
            clickSound.currentTime = 0;
            clickSound.play().then(() => {
                console.log('Sound played successfully');
            }).catch(err => {
                console.error('Error playing sound:', err);
            });
        });
    } else {
        console.error('Could not find soundButton or clickSound');
    }
});
