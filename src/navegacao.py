import time
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from irobot_create_msgs.action import Dock, Undock


class Navegador:
    """Controla a movimentação do robô pelo mapa e a volta pra doca."""

    def __init__(self, robo, ns):
        self.robo = robo
        self.navegando = False
        self.goal_handle = None
        self.tempo_envio = 0.0

        self.nav_client = ActionClient(robo, NavigateToPose, f'{ns}/navigate_to_pose')
        self.dock_client = ActionClient(robo, Dock, f'{ns}/dock')
        self.undock_client = ActionClient(robo, Undock, f'{ns}/undock')

    def sair_da_doca(self):
        self.robo.get_logger().info("Saindo da doca...")
        self.robo.undock_timer = self.robo.create_timer(0.5, self._enviar_undock)

    def _enviar_undock(self):
        self.robo.undock_timer.cancel()
        if not self.undock_client.wait_for_server(timeout_sec=5.0):
            self.robo.get_logger().warn("Servidor de undock não encontrado. Continuando sem undock...")
            self.robo.iniciar_missao()
            return
        self.undock_client.send_goal_async(Undock.Goal()).add_done_callback(self._undock_aceito)

    def _undock_aceito(self, future):
        handle = future.result()
        if handle.accepted:
            handle.get_result_async().add_done_callback(self._undock_pronto)
        else:
            self.robo.get_logger().warn("Undock recusado. Continuando sem undock...")
            self.robo.iniciar_missao()

    def _undock_pronto(self, future):
        self.robo.get_logger().info("Saiu da doca. Iniciando missao...")
        self.robo.iniciar_missao()

    def ir_para(self, x, y):
        self.robo.get_logger().info(f"Navegando para X:{x}, Y:{y}")
        self.nav_client.wait_for_server()
        self.navegando = True
        self.tempo_envio = time.time()
        self.goal_handle = None

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y

        # Orientacao neutra: o robo gira ao chegar pra achar o QR Code
        goal.pose.pose.orientation.z = 0.0
        goal.pose.pose.orientation.w = 1.0

        self.nav_client.send_goal_async(
            goal, feedback_callback=self.feedback
        ).add_done_callback(self.goal_aceito)

    def feedback(self, feedback_msg):
        # Ignora os primeiros 5s pq pode ser informação da rota anterior
        if time.time() - self.tempo_envio < 5.0:
            return
        dist = feedback_msg.feedback.distance_remaining
        if self.navegando and dist < 0.5:
            self.navegando = False
            self.robo.get_logger().info(f"Perto o suficiente ({dist:.2f}m). Procurando QR Code...")
            if self.goal_handle:
                self.goal_handle.cancel_goal_async()
            self.robo.camera.ativo = True

    def goal_aceito(self, future):
        self.goal_handle = future.result()
        if self.goal_handle.accepted:
            self.robo.get_logger().info("Nav2 aceitou a rota.")
            self.goal_handle.get_result_async().add_done_callback(self.nav_concluida)
        else:
            self.robo.get_logger().error("Nav2 recusou a rota.")
            self.robo.camera.ativo = True

    def nav_concluida(self, future):
        if self.navegando:
            self.robo.get_logger().info("Nav2 concluiu a rota. Procurando QR Code...")
            self.robo.camera.ativo = True

    def voltar_doca(self):
        self.robo.get_logger().info("Missão completa. Voltando pra doca...")
        # Usa timer pra sair do contexto do callback bloqueante antes de mandar o goal
        self.robo.dock_timer = self.robo.create_timer(0.5, self._enviar_dock)

    def _enviar_dock(self):
        # Cancela o timer pra nao repetir
        self.robo.dock_timer.cancel()

        self.robo.get_logger().info("Procurando servidor de doca...")
        if not self.dock_client.wait_for_server(timeout_sec=5.0):
            self.robo.get_logger().warn("Servidor de doca não encontrado. Encerrando...")
            return
        self.robo.get_logger().info("Enviando comando de doca...")
        self.dock_client.send_goal_async(Dock.Goal()).add_done_callback(self.aceito_dock)

    def aceito_dock(self, future):
        handle = future.result()
        if handle.accepted:
            handle.get_result_async().add_done_callback(self.finalizar_dock)

    def finalizar_dock(self, future):
        self.robo.get_logger().info("Robo docado com sucesso. Encerrando...")
        self.robo.get_logger().info("Fim de execução.")
        raise SystemExit(0)
