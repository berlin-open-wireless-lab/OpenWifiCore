if docker ps &>/dev/null; then
        DOCKER_CMD="docker"
elif sudo docker ps &>/dev/null; then
        DOCKER_CMD="sudo docker"
else
        echo "ERROR finding docker command!"
        return -1
fi
