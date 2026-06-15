FROM osrf/ros:humble-desktop

ARG user_id=1000
ARG ros_ws=/home/dockeruser/turtlebot4_ws

ENV DEBIAN_FRONTEND=noninteractive

# 1. ROS + YOLO e Python + cv_bridge
RUN apt-get update && apt-get install -y \
    ignition-fortress \
    ros-humble-ros-gz \
    ros-humble-gz-ros2-control \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-turtlebot4-simulator \
    ros-humble-irobot-create-nodes \
    ros-humble-turtlebot4-navigation \
    ros-humble-turtlebot4-description \
    ros-humble-turtlebot4-viz \
    ros-humble-teleop-twist-keyboard \
    ros-humble-twist-mux \
    ros-humble-nav2-bringup \
    ros-humble-nav2-msgs \
    ros-humble-slam-toolbox \
    ros-humble-rviz2 \
    ros-humble-cv-bridge \
    python3-pip \
    python3-opencv \
    libgl1 \
    libglib2.0-0 \
    nano \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalação do PyTorch, YOLOv8 e dependências matemáticas
RUN pip3 install --no-cache-dir ultralytics "numpy<2"

# 3. Permissões de GPU
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=all

# 4. Configuração do usuário e paths
RUN useradd -m --uid ${user_id} dockeruser
USER dockeruser
WORKDIR /home/dockeruser
ENV HOME=/home/dockeruser
ENV PATH="/home/dockeruser/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# 5. Estrutura do workspace
RUN mkdir -p ${ros_ws}/src

# 6. Configurações obrigatórias do TurtleBot4 e ROS2
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc \
    && echo "export TURTLEBOT4_MODEL=standard" >> ~/.bashrc \
    && echo "export ROS_DOMAIN_ID=0" >> ~/.bashrc \
    && echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> ~/.bashrc \
    && echo "export IGN_VERSION=fortress" >> ~/.bashrc \
    && echo "export IGNITION_VERSION=fortress" >> ~/.bashrc

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]