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
                    sh "docker tag rtechsupport/techsupport-bot:prod rtechsupport/techsupport-bot:${env.GIT_COMMIT_SHORT}"
                    sh "docker push rtechsupport/techsupport-bot:${env.GIT_COMMIT_SHORT}"
                }
            }
        }
    }
}
