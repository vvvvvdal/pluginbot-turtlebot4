import cv2
import rclpy
import time
from rclpy.node import Node
from geometry_msgs.msg import Twist
from navegacao import Navegador
from camera import Leitor_De_Camera

# Pontos de parada da rota de inspeção: (x, y) em metros no mapa.
# NOTA: No mundo real, edite as coordenadas abaixo para os pontos reais do ambiente.
# A orientação não é definida aqui pois o robô gira automaticamente ao chegar
# para encontrar o QR Code com a câmera.
ROTA = [
    (-2.5, 0.5),  # Perto do Cubo A (centro em -3.0, 0.5)
    (1.5,  1.0)   # Perto do Cubo B (centro em 2.0, 1.0)
]


class Robo_Inspector(Node):
    """Controla a inspeção do robo e interage com o agente."""

    def __init__(self):
        super().__init__('robo_inspector')
        
        # Parâmetros que permitem adaptar entre Simulação (Gazebo) e Robô Real
        # Para rodar no real: python3 src/inspecao.py --ros-args -p use_sim_time:=false -p namespace:=turtlebot4
        self.declare_parameter('namespace', '/turtlebot1')
        
        ns_param = self.get_parameter('namespace').get_parameter_value().string_value
        # Formata pra garantir que inicia com barra e não dá erro, ou deixa em branco
        self.ns = f"/{ns_param.strip('/')}" if ns_param.strip('/') else ""

        self.indice_rota = 0
        self.status = ""
        self.pub_vel = self.create_publisher(Twist, f'{self.ns}/cmd_vel', 10)

        self.navegador = Navegador(self, self.ns)
        self.camera = Leitor_De_Camera(self, self.pub_vel, self.ns)

        self.iniciou = False
        self.create_timer(2.0, self.iniciar_undock)

    def iniciar_undock(self):
        if self.iniciou:
            return
        self.iniciou = True
        self.get_logger().info("Iniciando inspecao. Saindo da doca...")
        self.navegador.sair_da_doca()

    def iniciar_missao(self):
        self.get_logger().info(f"Indo pro cubo {self.indice_rota+1}...")
        self.ir_proximo_ponto()

    def ir_proximo_ponto(self):
        self.status = ""
        if self.indice_rota < len(ROTA):
            x, y = ROTA[self.indice_rota]
            self.indice_rota += 1
            self.navegador.ir_para(x, y)
        else:
            self.get_logger().info("Missao completa. Voltando pra doca...")
            self.navegador.voltar_doca()

    def inspecionar_cubo(self):
        """Aproxima do cubo, analisa e volta pra trás."""
        self.get_logger().info("Defeito detectado. Iniciando inspecao...")

        # Mostra DEFEITO DETECTADO por 3 segundos parado
        self.status = "DEFEITO DETECTADO"
        self.camera.atualizar_tela()
        time.sleep(3.0)

        # Muda pra INSPECIONANDO durante os movimentos
        self.status = "INSPECIONANDO..."
        mov = Twist()

        # Se aproxima devagar do cubo
        self.get_logger().info("Aproximando do cubo...")
        mov.linear.x = 0.1
        mov.angular.z = 0.0
        self.mover_por_tempo(mov, 2.0)

        # Para e analisa (simula leitura de sensor)
        self.pub_vel.publish(Twist())
        self.get_logger().info("Analisando o cubo...")
        time.sleep(3.0)

        # Scan lateral rapido
        self.get_logger().info("Escaneando...")
        mov.linear.x = 0.0
        mov.angular.z = 0.4
        self.mover_por_tempo(mov, 1.0)
        mov.angular.z = -0.4
        self.mover_por_tempo(mov, 2.0)
        mov.angular.z = 0.4
        self.mover_por_tempo(mov, 1.0)

        # Dá ré pra distância segura
        self.get_logger().info("Recuando...")
        mov.linear.x = -0.1
        mov.angular.z = 0.0
        self.mover_por_tempo(mov, 2.0)

        # Mostra TUDO CERTO por 4 segundos parado
        self.pub_vel.publish(Twist())
        self.status = "TUDO CERTO"
        self.camera.atualizar_tela()
        self.get_logger().info("Inspecao pronta. Proximo ponto...")
        time.sleep(4.0)

        self.status = ""
        self.ir_proximo_ponto()

    def mover_por_tempo(self, comando, duracao):
        t0 = time.time()
        while time.time() - t0 < duracao:
            self.pub_vel.publish(comando)
            self.camera.atualizar_tela()
            time.sleep(0.1)


def main(args=None):
    rclpy.init(args=args)
    no = Robo_Inspector()
    try:
        rclpy.spin(no)
    except KeyboardInterrupt:
        pass
    finally:
        no.destroy_node()
        cv2.destroyAllWindows()
        rclpy.shutdown()


if __name__ == "__main__":
    main()