let isRepoProcessed = false;

async function handleSubmit(event) {
    event.preventDefault(); // Prevent form from reloading the page

    if (!isRepoProcessed) {
        // First step: Process the GitHub repository
        await processRepository();
    } else {
        // Second step: Ask question about the repository
        await askQuestion();
    }
}

async function processRepository() {
    const repoUrlInput = document.getElementById('repo-url');
    const repoUrl = repoUrlInput.value.trim();

    if (!repoUrl) {
        alert("Please enter a GitHub repository URL.");
        return;
    }

    try {
        const formData = new FormData();
        formData.append('github_url', repoUrl);
        
        const response = await fetch('/', {
            method: 'POST',
            body: formData
        });

        const result = await response.text();
        
        // Show success message or handle response
        alert(result || "Repository processed successfully!");
        
        // Freeze the repository URL input
        repoUrlInput.disabled = true;
        repoUrlInput.style.backgroundColor = '#f0f0f0';
        repoUrlInput.style.cursor = 'not-allowed';
        
        // Show the question container
        document.getElementById('question-container').style.display = 'block';
        
        // Update button text
        document.getElementById('submit-btn').textContent = 'Ask Question';
        
        // Update state
        isRepoProcessed = true;
        
        // Focus on the question textarea
        document.getElementById('question').focus();
        
    } catch (error) {
        console.error('Error processing repository:', error);
        alert('Failed to process repository. Please try again.');
    }
}

async function askQuestion() {
    const questionInput = document.getElementById('question');
    const question = questionInput.value.trim();
    const repoUrl = document.getElementById('repo-url').value.trim();

    if (!question) {
        alert("Please enter a question!");
        return;
    }

    try {
        const formData = new FormData();
        formData.append('github_url', repoUrl);
        formData.append('query', question);
        
        const response = await fetch('/ask', {
            method: 'POST',
            body: formData
        });

        const result = await response.text();
        alert(result); // Replace with better UI in production
        
        // Clear the question for next question
        questionInput.value = '';
        
    } catch (error) {
        console.error('Error asking question:', error);
        alert('Failed to get answer. Please try again.');
    }
}