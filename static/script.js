// WAEC CBT Platform JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Keyboard Shortcuts
    document.addEventListener('keydown', function(e) {
        // Multiple choice options
        if (e.key >= 'A' && e.key <= 'D') {
            const option = document.querySelector(`input[value="${e.key}"]`);
            if (option) {
                option.checked = true;
                saveAnswer();
            }
        }
        
        // Navigation shortcuts
        switch(e.key.toLowerCase()) {
            case 'n':
                navigateToNext();
                break;
            case 'p':
                navigateToPrevious();
                break;
        }
    });

    // Navigation Functions
    function navigateToNext() {
        const nextBtn = document.querySelector('.btn-next');
        if (nextBtn) nextBtn.click();
    }

    function navigateToPrevious() {
        const prevBtn = document.querySelector('.btn-prev');
        if (prevBtn) prevBtn.click();
    }

    // Auto-save answers
    function saveAnswer() {
        const currentQuestion = document.querySelector('.current-question');
        if (!currentQuestion) return;

        const answer = getCurrentAnswer();
        if (answer) {
            // Simulate saving to server
            console.log('Saving answer:', answer);
            
            // Update question status
            updateQuestionStatus('answered');
        }
    }

    function getCurrentAnswer() {
        // For multiple choice
        const selectedOption = document.querySelector('input[name="answer"]:checked');
        if (selectedOption) {
            return selectedOption.value;
        }
        
        // For essay questions
        const textarea = document.querySelector('textarea');
        if (textarea && textarea.value.trim()) {
            return textarea.value;
        }
        
        return null;
    }

    function updateQuestionStatus(status) {
        const currentQuestionNumber = document.querySelector('.question-number.active');
        if (currentQuestionNumber) {
            currentQuestionNumber.classList.remove('skipped', 'answered');
            currentQuestionNumber.classList.add(status);
        }
    }

    // Timer functionality (for exam pages)
    function initializeTimer(minutes) {
        let timeLeft = minutes * 60;
        const timerElement = document.querySelector('.timer');
        
        if (!timerElement) return;
        
        const timerInterval = setInterval(() => {
            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                autoSubmitExam();
                return;
            }
            
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            timerElement.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            timeLeft--;
        }, 1000);
    }

    function autoSubmitExam() {
        if (confirm('Time is up! Your exam will be submitted automatically.')) {
            // Submit all answers
            document.querySelector('form').submit();
        }
    }

    // Question navigation
    document.querySelectorAll('.question-number').forEach(number => {
        number.addEventListener('click', function() {
            // Remove active class from all numbers
            document.querySelectorAll('.question-number').forEach(n => {
                n.classList.remove('active');
            });
            
            // Add active class to clicked number
            this.classList.add('active');
            
            // Load question content (simulated)
            loadQuestion(this.textContent);
        });
    });

    function loadQuestion(questionNumber) {
        // In a real application, this would fetch the question from the server
        console.log('Loading question:', questionNumber);
        
        // Update URL without reloading page
        history.pushState(null, '', `/question/${questionNumber}`);
    }

    // Initialize exam timer if on exam page
    const examSection = document.querySelector('.exam-content');
    if (examSection) {
        // Get time from data attribute or default to 60 minutes
        const examTime = document.body.dataset.examTime || 60;
        initializeTimer(examTime);
    }

    // Answer change listeners
    document.querySelectorAll('input[type="radio"]').forEach(radio => {
        radio.addEventListener('change', saveAnswer);
    });

    document.querySelectorAll('textarea').forEach(textarea => {
        textarea.addEventListener('input', function() {
            // Debounce saving for essay questions
            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(saveAnswer, 1000);
        });
    });

    // Navigation button handlers
    document.querySelectorAll('.btn-next').forEach(btn => {
        btn.addEventListener('click', function() {
            const currentActive = document.querySelector('.question-number.active');
            if (currentActive && currentActive.nextElementSibling) {
                currentActive.nextElementSibling.click();
            }
        });
    });

    document.querySelectorAll('.btn-prev').forEach(btn => {
        btn.addEventListener('click', function() {
            const currentActive = document.querySelector('.question-number.active');
            if (currentActive && currentActive.previousElementSibling) {
                currentActive.previousElementSibling.click();
            }
        });
    });

    // Real-time Timer Implementation
    class ExamTimer {
        constructor(sectionId) {
            this.sectionId = sectionId;
            this.timeLeft = 0;
            this.timerElement = null;
            this.interval = null;
            this.initialize();
        }

        async initialize() {
            try {
                const response = await fetch(`/api/timer/${this.sectionId}`);
                const data = await response.json();
                this.timeLeft = data.time_allowed;
                this.timerElement = document.querySelector('.timer-display');
                this.startTimer();
            } catch (error) {
                console.error('Failed to initialize timer:', error);
            }
        }

        startTimer() {
            this.interval = setInterval(() => {
                this.timeLeft--;
                this.updateDisplay();
                
                if (this.timeLeft <= 0) {
                    this.timeUp();
                }
                
                // Warning at 5 minutes left
                if (this.timeLeft === 300) {
                    this.showWarning('5 minutes remaining!');
                }
                
                // Warning at 1 minute left  
                if (this.timeLeft === 60) {
                    this.showWarning('1 minute remaining!');
                }
            }, 1000);
        }

        updateDisplay() {
            if (!this.timerElement) return;
            
            const minutes = Math.floor(this.timeLeft / 60);
            const seconds = this.timeLeft % 60;
            this.timerElement.textContent = `[ ${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')} ]`;
            
            // Change color when time is running out
            if (this.timeLeft < 300) {
                this.timerElement.style.color = '#e74c3c';
                this.timerElement.style.fontWeight = 'bold';
            }
        }

        showWarning(message) {
            const warning = document.createElement('div');
            warning.className = 'time-warning';
            warning.textContent = message;
            warning.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #e74c3c;
                color: white;
                padding: 15px;
                border-radius: 5px;
                z-index: 1000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            `;
            document.body.appendChild(warning);
            
            setTimeout(() => {
                warning.remove();
            }, 5000);
        }

        timeUp() {
            clearInterval(this.interval);
            alert('Time is up! Your exam will be submitted automatically.');
            // Auto-submit the exam
            window.location.href = '/finish_exam';
        }

        destroy() {
            clearInterval(this.interval);
        }
    }

    // Initialize timer on exam pages
    if (document.querySelector('.exam-content')) {
        const sectionId = window.location.pathname.split('/').pop();
        window.examTimer = new ExamTimer(sectionId);
    }

    // Auto-save progress every 30 seconds
    setInterval(() => {
        if (document.querySelector('.exam-content')) {
            saveAllAnswers();
        }
    }, 30000);

    function saveAllAnswers() {
        const answers = {};
        document.querySelectorAll('input[type="radio"]:checked, textarea').forEach(element => {
            const questionId = element.closest('.question-item')?.querySelector('.question-number')?.textContent;
            if (questionId) {
                answers[questionId] = element.type === 'radio' ? element.value : element.value;
            }
        });
        
        // Send to server
        fetch('/api/save_answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(answers)
        });
    }
});