// WAEC Exam Functionality
class ExamController {
    constructor() {
        this.currentQuestion = 1;
        this.totalQuestions = parseInt(document.getElementById('examData').dataset.totalQuestions);
        this.sectionId = document.getElementById('examData').dataset.sectionId;
        this.timeAllowed = parseInt(document.getElementById('examData').dataset.timeAllowed);
        this.timeLeft = this.timeAllowed;
        this.timerInterval = null;
        
        this.initializeEventListeners();
        this.startTimer();
        this.loadQuestion(this.currentQuestion);
    }

    initializeEventListeners() {
        // Question navigation
        document.getElementById('prevQuestion').addEventListener('click', () => this.previousQuestion());
        document.getElementById('nextQuestion').addEventListener('click', () => this.nextQuestion());
        document.getElementById('finishSection').addEventListener('click', () => this.finishSection());

        // Question number clicks
        document.querySelectorAll('.question-number').forEach(element => {
            element.addEventListener('click', (e) => {
                const questionNumber = parseInt(e.target.dataset.questionNumber);
                this.loadQuestion(questionNumber);
            });
        });

        // Answer changes
        document.addEventListener('change', (e) => {
            if (e.target.name === 'answer' || e.target.id === 'essayAnswer') {
                this.saveAnswer();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });
    }

    handleKeyboardShortcuts(e) {
        switch(e.key.toUpperCase()) {
            case 'A':
            case 'B':
            case 'C':
            case 'D':
                this.selectMultipleChoice(e.key.toUpperCase());
                break;
            case 'N':
                e.preventDefault();
                this.nextQuestion();
                break;
            case 'P':
                e.preventDefault();
                this.previousQuestion();
                break;
        }
    }

    selectMultipleChoice(option) {
        const radio = document.querySelector(`input[value="${option}"]`);
        if (radio) {
            radio.checked = true;
            this.saveAnswer();
        }
    }

    async loadQuestion(questionNumber) {
        this.currentQuestion = questionNumber;
        
        try {
            const response = await fetch(`/api/question/${this.sectionId}/${questionNumber}`);
            const data = await response.json();
            
            this.updateQuestionDisplay(data);
            this.updateNavigation();
            this.updateQuestionNumbers();
            
        } catch (error) {
            console.error('Error loading question:', error);
        }
    }

    updateQuestionDisplay(questionData) {
        document.getElementById('currentQuestionNumber').textContent = questionData.question_number;
        document.getElementById('questionText').innerHTML = questionData.question_text.replace(/\n/g, '<br>');
        
        // Update answer area based on question type
        this.renderAnswerArea(questionData);
    }

    renderAnswerArea(questionData) {
        const answerArea = document.querySelector('.answer-area');
        
        if (questionData.question_type === 'essay') {
            answerArea.innerHTML = `
                <textarea id="essayAnswer" placeholder="Type your answer here..." rows="10">${questionData.current_answer || ''}</textarea>
            `;
        } else if (questionData.question_type === 'multiple_choice') {
            let optionsHtml = '';
            ['a', 'b', 'c', 'd'].forEach(option => {
                if (questionData[`option_${option}`]) {
                    const isChecked = questionData.current_answer === option.toUpperCase();
                    optionsHtml += `
                        <div class="option">
                            <input type="radio" id="option${option.toUpperCase()}" name="answer" value="${option.toUpperCase()}" ${isChecked ? 'checked' : ''}>
                            <label for="option${option.toUpperCase()}">${option.toUpperCase()}. ${questionData[`option_${option}`]}</label>
                        </div>
                    `;
                }
            });
            answerArea.innerHTML = `<div class="options-area">${optionsHtml}</div>`;
        }
    }

    updateNavigation() {
        document.getElementById('prevQuestion').style.display = this.currentQuestion > 1 ? 'block' : 'none';
        document.getElementById('nextQuestion').style.display = this.currentQuestion < this.totalQuestions ? 'block' : 'none';
        document.getElementById('finishSection').style.display = this.currentQuestion === this.totalQuestions ? 'block' : 'none';
    }

    updateQuestionNumbers() {
        document.querySelectorAll('.question-number').forEach(element => {
            element.classList.remove('active');
            if (parseInt(element.dataset.questionNumber) === this.currentQuestion) {
                element.classList.add('active');
            }
        });
    }

    async saveAnswer() {
        const answer = this.getCurrentAnswer();
        if (!answer) return;

        try {
            await fetch('/api/save_answer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    section_id: this.sectionId,
                    question_number: this.currentQuestion,
                    answer: answer
                })
            });

            // Update question status
            const currentQuestionElement = document.querySelector(`.question-number[data-question-number="${this.currentQuestion}"]`);
            currentQuestionElement.classList.add('answered');
            currentQuestionElement.classList.remove('skipped');

        } catch (error) {
            console.error('Error saving answer:', error);
        }
    }

    getCurrentAnswer() {
        if (document.getElementById('essayAnswer')) {
            return document.getElementById('essayAnswer').value.trim();
        } else {
            const selectedOption = document.querySelector('input[name="answer"]:checked');
            return selectedOption ? selectedOption.value : null;
        }
    }

    previousQuestion() {
        if (this.currentQuestion > 1) {
            this.loadQuestion(this.currentQuestion - 1);
        }
    }

    nextQuestion() {
        if (this.currentQuestion < this.totalQuestions) {
            this.loadQuestion(this.currentQuestion + 1);
        }
    }

    startTimer() {
        this.timerInterval = setInterval(() => {
            this.timeLeft--;
            this.updateTimerDisplay();
            
            if (this.timeLeft <= 0) {
                this.timeUp();
            }
            
            // Warning at 5 minutes and 1 minute
            if (this.timeLeft === 300 || this.timeLeft === 60) {
                this.showTimeWarning();
            }
        }, 1000);
    }

    updateTimerDisplay() {
        const minutes = Math.floor(this.timeLeft / 60);
        const seconds = this.timeLeft % 60;
        document.getElementById('examTimer').textContent = `[ ${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')} ]`;
        
        // Change color when time is running out
        if (this.timeLeft < 300) {
            document.getElementById('examTimer').style.color = '#e74c3c';
            document.getElementById('examTimer').style.fontWeight = 'bold';
        }
    }

    showTimeWarning() {
        const minutes = Math.floor(this.timeLeft / 60);
        const warning = document.createElement('div');
        warning.className = 'time-warning';
        warning.textContent = `${minutes} minute${minutes !== 1 ? 's' : ''} remaining!`;
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
        clearInterval(this.timerInterval);
        alert('Time is up! Your exam will be submitted automatically.');
        this.finishSection();
    }

    finishSection() {
        if (confirm('Are you sure you want to finish this section? You cannot return once finished.')) {
            window.location.href = `/complete_section/${this.sectionId}`;
        }
    }
}

// Initialize exam when page loads
document.addEventListener('DOMContentLoaded', () => {
    new ExamController();
});