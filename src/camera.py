import cv2
import time
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image
from agente import Agente


class Leitor_De_Camera:
    """Lê a câmera do robô e tenta detectar QR Codes."""

    def __init__(self, robo, pub_vel, ns):
        self.robo = robo
        self.pub_vel = pub_vel
        self.ativo = False
        self.ultimo_frame = None

        self.bridge = CvBridge()
        self.agente = Agente()
        self.detector = cv2.QRCodeDetector()

        # O tópico assume o namespace passado. Pode ser ajustado caso a câmera
        # real tenha um caminho levemente diferente, mas a estrutura se mantém.
        robo.create_subscription(
            Image,
            f'{ns}/oakd/rgb/preview/image_raw',
            self.callback,
            10
        )

    def callback(self, img):
        frame = self.bridge.imgmsg_to_cv2(img, "bgr8")
        self.ultimo_frame = frame.copy()

        if self.ativo:
            dados, _, _ = self.detector.detectAndDecode(frame)

            if dados:
                self.ativo = False
                self.pub_vel.publish(Twist())

                self.robo.get_logger().info("Aguardando 5 segundos...")
                time.sleep(5.0)

                self.robo.get_logger().info(f"QR Code lido: {dados}")
                resposta = self.agente.interpretar_ordem(dados)
                self.robo.get_logger().info(f"Decisao do agente: {resposta['action']}")

                if resposta['action'] == 'fix':
                    self.robo.status = "DEFEITO DETECTADO"
                    self.desenhar_status(frame)
                    cv2.imshow("Camera do Robo", frame)
                    cv2.waitKey(1)
                    self.robo.inspecionar_cubo()
                else:
                    self.robo.status = "TUDO CERTO"
                    self.desenhar_status(frame)
                    cv2.imshow("Camera do Robo", frame)
                    cv2.waitKey(1)
                    time.sleep(4.0)
                    self.robo.get_logger().info("Tudo certo. Indo pro proximo ponto...")
                    self.robo.ir_proximo_ponto()
                return
            else:
                # Gira devagar até achar o QR Code
                mov = Twist()
                mov.angular.z = 0.3
                self.pub_vel.publish(mov)

        self.desenhar_status(frame)
        cv2.imshow("Camera do Robo", frame)
        cv2.waitKey(1)

    def desenhar_status(self, frame):
        """Mostra o status na tela da câmera (só quando tem algo pra mostrar)."""
        
        texto = self.robo.status
        if not texto:
            return

        # Cor: verde = ok, vermelho = defeito, laranja = inspecionando
        if "DEFEITO" in texto:
            cor = (0, 0, 255)
        elif "TUDO CERTO" in texto:
            cor = (0, 255, 0)
        else:
            cor = (0, 165, 255)  # Laranja

        cv2.rectangle(frame, (5, 5), (350, 40), (0, 0, 0), -1)
        cv2.putText(frame, texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)

    def atualizar_tela(self):
        """Atualiza a janela da câmera com o último frame e o status atual."""

        if self.ultimo_frame is not None:
            frame = self.ultimo_frame.copy()
            self.desenhar_status(frame)
            cv2.imshow("Camera do Robo", frame)
            cv2.waitKey(1)
