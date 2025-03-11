# Chopper - Bot de Verificação para Discord

Chopper é um bot para Discord projetado para verificar a idade de novos membros automaticamente, garantindo que apenas maiores de 18 anos permaneçam no servidor. Ele utiliza um sistema de verificação de aniversário e pode registrar logs em um canal específico.

## Recursos

- **Verificação automática de idade:** Ao entrar no servidor, o bot solicita a verificação via DM.
- **Banimento automático:** Usuários abaixo de 18 anos são banidos automaticamente.
- **Canal temporário de verificação:** O bot cria um canal exclusivo para a verificação de cada usuário.
- **Logs de moderação:** Registra ações de verificação e banimentos em um canal configurado.
- **Comandos interativos:** Consulta, adiciona, edita e remove aniversários.

## Instalação

Adicione o Chopper ao seu servidor utilizando o link abaixo:

[Adicionar ao Discord](https://discord.com/api/oauth2/authorize?client_id=1333034229914796115&permissions=8&scope=bot)

## Comandos Principais

- **`/chopper_log <canal>`:** Define um canal para armazenar os logs das verificações.
- **`/age <usuário>`:** Consulta a data de aniversário de um usuário.
- **`/age_add <usuário> <data>`:** Adiciona a data de aniversário de um usuário.
- **`/age_edit <usuário> <nova_data>`:** Edita a data de aniversário registrada para um usuário.
- **`/age_delete <usuário>`:** Remove a data de aniversário de um usuário.
- **`/age_list`:** Lista todos os aniversários registrados.
- **`/age_id_verified <usuário>`:** Marca um usuário como verificado.
- **`/verify [usuário]`:** Inicia o processo de verificação via DM para o usuário (ou para outro, se especificado).

## Configuração e Uso

1. **Convide o bot para o seu servidor** através do link de instalação.
2. **Configure o canal de logs** usando o comando `/chopper_log <#canal>`.
3. **Verificação automática:** Quando um novo membro entra, o bot cria um canal temporário e solicita a data de aniversário.
4. **Administração:** Use os comandos para gerenciar os registros de aniversários conforme necessário.

## Tecnologias Utilizadas

- Python
- discord.py
- SQLite
- dotenv

## Contribuição

Sinta-se à vontade para contribuir! Abra uma issue ou envie um pull request com melhorias.

## Licença

Este projeto está sob a licença MIT.
