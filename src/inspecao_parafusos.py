import cv2
import sys
import select
import rclpy
from ultralytics import YOLO
from rclpy.node import Node
from rclpy.action import ActionClient
from sensor_msgs.msg import Image, BatteryState
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
from irobot_create_msgs.action import Dock
from nav2_msgs.action import NavigateToPose

DISTANCIA_MINIMA = 1.5
LIMITE_BATERIA_BAIXA = 0.20

class Visao_YOLO:
    def __init__(self):
        self.modelo_yolo = YOLO('yolov8n.pt')

    def processar_imagem(self, imagem_cv2):
        # 2. Inferencia da IA do modelo YOLO
        resultados = self.modelo_yolo(imagem_cv2, verbose=False)
        imagem_desenhada = resultados[0].plot()

        pessoa = False
        x_centro, y_centro = 0, 0

        # 3. Processamento de coordenadas
        for caixa in resultados[0].boxes:
            if int(caixa.cls[0].item()) == 0: # ID 0 = Pessoa
                x_centro = int(caixa.xywh[0][0].item())
                y_centro = int(caixa.xywh[0][1].item())
                pessoa = True
                break

        return pessoa, x_centro, y_centro, imagem_desenhada


class Olho_Do_Robo(Node):
    def __init__(self) -> None:
        super().__init__('Olho_Do_Robo')

        self.bridge = CvBridge()
        self.visao = Visao_YOLO()

        # Variaveis de memoria do robo
        self.mapa_profundidade = None
        self.fugindo = False 
        self.indo_para_o_dock = False
        self.navegando_autonomo = False

        # Ouvinte da camera rgb (visão)
        self.subscription_velocidade = self.create_subscription(
            Image, '/turtlebot1/oakd/rgb/preview/image_raw', self.ouvinte_callback, 10)

        # Ouvinte da camera de profundidade (distancia)
        self.subscription_profundidade = self.create_subscription(
            Image, '/turtlebot1/oakd/rgb/preview/depth', self.profundidade_callback, 10)

        # Ouvinte do Status da Bateria
        self.subscription_bateria = self.create_subscription(
            BatteryState, '/turtlebot1/battery_state', self.bateria_callback, 10)

        # Falante do robo (controle de rodas)
        self.publisher_velocidade = self.create_publisher(Twist, '/turtlebot1/cmd_vel_vision', 10)

        # Clientes de Action (Dock e Nav2)
        self.dock_client = ActionClient(self, Dock, '/turtlebot1/dock')
        self.nav_client = ActionClient(self, NavigateToPose, '/turtlebot1/navigate_to_pose')

        # Checador de comando do terminal
        self.create_timer(0.5, self.checar_input_terminal)
        self.get_logger().info("No Ativo. Digite 'coordenada(X,Y)' ou use o RViz2.")

    def ouvinte_callback(self, img):
        # 1. Traducao da imagem
        imagem_cv2 = self.bridge.imgmsg_to_cv2(img, "bgr8")
        pessoa, x_centro, y_centro, imagem_desenhada = self.visao.processar_imagem(imagem_cv2)

        # 4. Controle de seguranca ao detectar pessoa proxima
        if pessoa and self.mapa_profundidade is not None:
            distancia_atual = self.calcular_distancia(y_centro, x_centro)

            if distancia_atual <= 0.0:
                pass
            elif distancia_atual <= DISTANCIA_MINIMA: 
                self.get_logger().warn(f"[ALERTA] Pessoa a {distancia_atual:.2f}m. Recuando.")
                if self.navegando_autonomo:
                    self.cancelar_navegacao()

                msg_movimento = Twist()
                msg_movimento.linear.x = -0.25 
                self.publisher_velocidade.publish(msg_movimento)
                self.fugindo = True 
            else: 
                if self.fugindo: 
                    self.get_logger().info("Distancia segura restabelecida. Parando.")
                    self.publisher_velocidade.publish(Twist())
                    self.fugindo = False 

        # 5. Exibicao na Tela
        cv2.imshow("Camera do robo", imagem_desenhada)
        cv2.waitKey(1)
    
    def profundidade_callback(self, img_profundidade):
        self.mapa_profundidade = self.bridge.imgmsg_to_cv2(img_profundidade, "passthrough")

    def calcular_distancia(self, y: int, x: int) -> float:
        try:
            altura, largura = self.mapa_profundidade.shape[:2]
            y, x = min(y, altura - 1), min(x, largura - 1)
            valor_pixel = self.mapa_profundidade[y, x]
            return float(valor_pixel) / 1000.0 if self.mapa_profundidade.dtype == 'uint16' else float(valor_pixel)
        except Exception:
            return 0.0

    # 6. Controle de retorno automatico por bateria critica
    def bateria_callback(self, msg):
        if msg.percentage <= LIMITE_BATERIA_BAIXA and not self.indo_para_o_dock:
            self.get_logger().error(f"Bateria baixa ({msg.percentage*100:.0f}%). Retornando a case.")
            self.indo_para_o_dock = True
            if self.navegando_autonomo:
                self.cancelar_navegacao()

            self.dock_client.wait_for_server()
            self.dock_client.send_goal_async(Dock.Goal())

    # 7. Controle de navegacao por insercao de comando ou coordenadas no terminal
    def checar_input_terminal(self):
        if self.indo_para_o_dock:
            return

        if select.select([sys.stdin], [], [], 0.0)[0]:
            linha = sys.stdin.readline().strip().lower()
            try:
                if linha.startswith("coordenada(") and linha.endswith(")"):
                    conteudo = linha.replace("coordenada(", "").replace(")", "")
                    partes = conteudo.split(",")
                else:
                    partes = linha.split()

                if len(partes) == 2:
                    self.ir_para_coordenada(float(partes[0].strip()), float(partes[1].strip()))
                else:
                    print("[ERRO] Formato aceito: coordenada(X,Y) ou X Y")
            except ValueError:
                print("[ERRO] Valores invalidos.")

    def ir_para_coordenada(self, x: float, y: float):
        self.get_logger().info(f"Navegando ate X: {x}, Y: {y}")
        self.nav_client.wait_for_server()

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.orientation.w = 1.0

        self.navegando_autonomo = True
        self.nav_client.send_goal_async(goal_msg).add_done_callback(self.resposta_nav_callback)

    def resposta_nav_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Meta recusada pelo Nav2.")
            self.navegando_autonomo = False
            return
        goal_handle.get_result_async().add_done_callback(self.resultado_nav_callback)

    def resultado_nav_callback(self, future):
        self.get_logger().info("Alvo alcancado.")
        self.navegando_autonomo = False

    def cancelar_navegacao(self):
        self.publisher_velocidade.publish(Twist())
        self.navegando_autonomo = False


def main(args=None):
    rclpy.init(args=args)
    olho_do_robo = Olho_Do_Robo()
    try:
        rclpy.spin(olho_do_robo)
    except KeyboardInterrupt:
        pass 
    finally:
        olho_do_robo.destroy_node()
        cv2.destroyAllWindows()
        rclpy.shutdown()

if __name__ == "__main__":
    main()