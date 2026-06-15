# Pluginbot - TurtleBot4

---

## Estrutura

- inspecao_parafusos.py: Visualização da câmera e visão computacional com YOLOv8.
- nav2.yaml: Parâmetros do Nav2 e configuração de mapa/sensores.
- twist_mux.yaml: Prioridade de comandos de movimentação.
- Dockerfile: Container com ROS 2, ferramentas de simulação e dependências de IA (YOLO).

---

# Como rodar

## 1. Clonar o repositório

```bash
git clone [https://github.com/vvvvvdal/turtlebot-inspecao.git](https://github.com/vvvvvdal/turtlebot-inspecao.git)

```

## 2. Entrar no diretório do projeto

```bash
cd turtlebot-inspecao/

```

---

## 3. Configuração NVIDIA

### Adicionar chave do repositório NVIDIA

```bash
curl -fsSL [https://nvidia.github.io/libnvidia-container/gpgkey](https://nvidia.github.io/libnvidia-container/gpgkey) | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L [https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list](https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list) | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

```

### Instalar NVIDIA Container Toolkit

```bash
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

```

### Configurar runtime NVIDIA no Docker

```bash
sudo nvidia-ctk runtime configure --runtime=docker

```

### Gerar arquivo CDI

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

```

### Reiniciar Docker

```bash
sudo systemctl restart docker

```

---

## 4. Permitir interface gráfica

Necessário para executar o Gazebo e o RViz2.

```bash
xhost +local:docker
```

---

## 5. Buildar container

```bash
docker build -t tb4_inspecao .
```

---

## 6. Rodar container

```bash
docker run --rm -it \
  --runtime=nvidia \
  --name tb4_inspecao \
  --env="NVIDIA_VISIBLE_DEVICES=all" \
  --env="NVIDIA_DRIVER_CAPABILITIES=all" \
  --env="DISPLAY=$DISPLAY" \
  --env="QT_X11_NO_MITSHM=1" \
  --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
  --volume="$(pwd):/home/dockeruser/ws" \
  --network=host \
  tb4_inspecao
```

---

# Fluxo de Execução

## Terminal 1: Gazebo

Inicializa o TurtleBot4 no ambiente de simulação.
(Nota: O modelo do robô foi adaptado para que a câmera OAK-D aponte para cima, em 90 graus.)

```bash
cd ws
colcon build --symlink-install
source install/setup.bash

ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py world:=warehouse namespace:=turtlebot1
```

```bash

# Em outro terminal
docker exec -it tb4_inspecao bash

# Opção 1: teste com sucesso (4 bolas verdes)
ros2 run ros_gz_sim create -file /home/dockeruser/ws/src/carro_sucesso.sdf

# Opção 2: Teste com falha (3 bolas verdes, faltando 1 bola verde)
ros2 run ros_gz_sim create -file /home/dockeruser/ws/src/carro_falha.sdf
```

---

## Terminal 2: SLAM

Inicializa o sistema de localização.

```bash
docker exec -it tb4_inspecao bash

ros2 launch turtlebot4_navigation slam.launch.py sync:=true namespace:=turtlebot1
```

---

## Terminal 3: Nav2

Inicializa o sistema de navegação autônoma utilizando os parâmetros locais.

```bash
docker exec -it tb4_inspecao bash

ros2 launch turtlebot4_navigation nav2.launch.py \
namespace:=turtlebot1 \
params_file:=/home/dockeruser/ws/src/nav2.yaml \
cmd_vel:=cmd_vel_nav
```

---

## Terminal 4: RViz2

Interface gráfica para visualização do mapa, posição dos waypoints de inspeção e feedback visual do robô.

Fixed Frame:

```text
turtlebot1/map

```

```bash
docker exec -it tb4_inspecao bash

ros2 launch turtlebot4_viz view_robot.launch.py namespace:=turtlebot1
```

---

## Terminal 5: Inspeção com YOLOv8

- Nó principal responsável por orquestrar a navegação entre os waypoints abaixo do veículo.
- Aciona a câmera apontada para cima em cada ponto estratégico.
- Detecta a presença/ausência de parafusos estruturais utilizando o modelo YOLOv8n.
- Gera relatório final no terminal com o status de cada ponto de inspeção.

```bash
docker exec -it tb4_inspecao bash

python3 ws/src/inspecao_parafusos.py
```

---

## Terminal 6: twist_mux

Define prioridade dos comandos de movimentação do robô.

```bash
docker exec -it tb4_inspecao bash

ros2 run twist_mux twist_mux \
--ros-args \
--params-file /home/dockeruser/ws/src/twist_mux.yaml \
-r cmd_vel_out:=/turtlebot1/cmd_vel
```