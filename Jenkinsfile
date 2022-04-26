pipeline {
    agent any
    environment {
        GIT_COMMIT_SHORT = sh(
                script: "printf \$(git rev-parse --short ${GIT_COMMIT})",
                returnStdout: true
        )
    }
    stages {
        stage('Build dev image') {
            steps {
                sh 'make dev'
            }
        }
        stage('Linting') {
            steps {
                sh 'make check-format'
                sh 'make lint'
            }
        }
        stage('Build prod image') {
            steps {
                sh 'make prod'
            }
        }
        stage('Docker Push') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub', passwordVariable: 'dockerHubPassword', usernameVariable: 'dockerHubUser')]) {
                    sh "docker login -u ${env.dockerHubUser} -p ${env.dockerHubPassword}"
                    sh "docker tag effprime/basement-bot:prod effprime/basement-bot:${env.GIT_COMMIT_SHORT}"
                    sh "docker push effprime/basement-bot:${env.GIT_COMMIT_SHORT}"
                }
            }
        }
    }
}
